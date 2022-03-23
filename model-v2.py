import networkx as nx
import yaml
import matplotlib.pyplot as plt


def read_config():
    with open("graphs/v2/2.yml") as f:
        config = yaml.safe_load(f)

    config["hardware"]["nodes"]["ingress"] = {"Q_num": 1, "Q_len": 1}
    config["hardware"]["nodes"]["egress"] = config["hardware"]["nodes"]["ingress"]
    for i in config["software"]:
        i["nodes"]["ingress"] = {"phy_node": "ingress", "partition": 1.0, "overhead": 0.0, "performance": None}
        i["nodes"]["egress"] = {"phy_node": "egress", "partition": 1.0, "overhead": 0.0, "performance": None}

    return config


def create_dag(use_case):
    dag = nx.DiGraph(**{k: v for k, v in use_case.items() if k != 'nodes' and k != 'edges'})
    dag.add_nodes_from(use_case['nodes'].items())
    for k, v in use_case['edges'].items():
        e = k.split("-")
        assert len(e) == 2 and e[0] in use_case['nodes'] and e[1] in use_case['nodes']
        dag.add_edge(e[0], e[1], **v)
    dag.graph['g_in'] = dag.graph['granularity-in'] / float(1 << 30)
    return dag


def calc_throughput():
    throughput = []
    bw_edges = {}
    interface = 0
    memory = 0
    for k, v in CONFIG["hardware"]["edges"].items():
        e = k.split("-")
        assert len(e) == 2 and e[0] in CONFIG["hardware"]['nodes'] and e[1] in CONFIG["hardware"]['nodes']
        e = tuple(sorted(e))
        bw_edges[e] = {"bw": v, "f": 0}
    for dag in use_cases:
        for k, v in dag.edges.items():
            ip_ip = tuple(sorted([dag.nodes[k[0]]['phy_node'], dag.nodes[k[1]]['phy_node']]))
            bw_edges[ip_ip]["f"] += v["total"]
            v["bw"] = bw_edges[ip_ip]["bw"]
            interface += v["INTF"]
            memory += v["DRAM"]

        for k, v in dag.nodes.items():
            if v["performance"] is None:
                continue
            total = sum([dag.edges[(i, k)]["total"] for i in dag.predecessors(k)])
            throughput.append({"v": v["performance"] * v["partition"] / total, "name": f"compute:{v['phy_node']}({k})"})

    for k, v in bw_edges.items():
        throughput.append({"v": v["bw"] / v["f"], "name": f"BW:{k[0]}-{k[1]}"})

    throughput.append({"v": CONFIG["hardware"]["interface"] / interface, "name": f"BW:interface"})
    throughput.append({"v": CONFIG["hardware"]["memory"] / memory, "name": f"BW:memory"})
    throughput.sort(key=lambda x: x['v'])

    print("throughput:")
    for i in throughput:
        print(f"%-20s\t\t{i['v']}" % i['name'])
    print("\n\n")

    return throughput[0]['v']


def calc_mm1n(rho, N: int) -> float:
    if rho == 1:
        return (N - 1) / 2
    try:
        return rho / (1 - rho) - N / (rho ** -N - 1)
    except (OverflowError, ZeroDivisionError):
        return rho / (1 - rho)


def calc_latency():
    for dag in use_cases:
        for k, v in dag.nodes.items():
            if v['performance'] is None:
                v['q_lat'] = 0.0
                v['lat'] = 0.0
                continue
            total = sum([dag.edges[(i, k)]["total"] for i in dag.predecessors(k)])
            rho = dag.in_degree(k) * dag.graph['bandwidth-in'] * total / (v['performance'] * v['partition'])
            lat = dag.graph['g_in'] * total / v['performance'] / v['partition']
            v['q_lat'] = calc_mm1n(rho, v['Q_num'] * v['Q_len']) * lat
            v['lat'] = v['q_lat'] + lat + v['overhead']

    latency = 0
    for dag in use_cases:
        for k, v in dag.edges.items():
            v['lat'] = dag.nodes[k[0]]['lat'] + v['total'] * dag.graph['g_in'] / v['bw']
        longest_path = nx.dag_longest_path(dag, 'lat')
        lat = nx.dag_longest_path_length(dag, 'lat')
        latency += lat
        print(longest_path)
        print(f"latency {lat * 10 ** 6} us")

    return latency / len(use_cases)


if __name__ == '__main__':
    CONFIG = read_config()
    use_cases = [create_dag(i) for i in CONFIG["software"]]
    P = calc_throughput()
    latencies = []
    M = 100
    for i in range(2 * M):
        use_cases[0].graph['bandwidth-in'] = P * i / M
        latencies.append(calc_latency() * 1E6)
    plt.plot(latencies)
    plt.show()
    pass
    # nx.draw(use_cases[0], pos=nx.spring_layout(use_cases[0]), with_labels=True)
    # plt.show()
