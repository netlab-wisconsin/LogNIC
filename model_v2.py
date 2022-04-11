import networkx as nx
import yaml
import matplotlib.pyplot as plt
from data import *


def read_config(yml_path):
    with open(yml_path) as yml:
        config = yaml.safe_load(yml)

    config["hardware"]["nodes"]["ingress"] = {"Q_num": 1, "Q_len": 1}
    config["hardware"]["nodes"]["egress"] = config["hardware"]["nodes"]["ingress"]
    for i in config["software"]:
        i["nodes"]["ingress"] = {"phy_node": "ingress", "partition": 1.0, "overhead": 0.0, "performance": None}
        i["nodes"]["egress"] = {"phy_node": "egress", "partition": 1.0, "overhead": 0.0, "performance": None}

    return config


def create_dags(use_cases):
    bw_sum = 0
    dags = []
    partition_sum = {}
    for use_case in use_cases:
        bw_sum += use_case['bandwidth-in']
        for i in use_case['nodes'].values():
            if i['phy_node'] not in partition_sum:
                partition_sum[i['phy_node']] = 0
            partition_sum[i['phy_node']] += i['partition']
    for use_case in use_cases:
        w = use_case['bandwidth-in'] / bw_sum if bw_sum != 0 else 1
        dag = nx.DiGraph(**{k: v for k, v in use_case.items() if k != 'nodes' and k != 'edges'})
        dag.add_nodes_from(use_case['nodes'].items())
        for v in dag.nodes.values():
            v['partition'] /= partition_sum[v['phy_node']] if partition_sum[v['phy_node']] else 1
        for k, v in use_case['edges'].items():
            e = k.split("-")
            assert len(e) == 2 and e[0] in use_case['nodes'] and e[1] in use_case['nodes']
            for key in v:
                v[key] *= w
            dag.add_edge(e[0], e[1], **v)
        dag.graph['g_in'] = dag.graph['granularity-in'] / float(1 << 30)
        dag.graph['weight'] = w
        dags.append(dag)
    return dags


def calc_throughput(hardware_cfg, use_cases, print_tag=False):
    throughput = []
    bw_edges = {}
    interface = 0
    memory = 0
    for k, v in hardware_cfg["edges"].items():
        e = k.split("-")
        assert len(e) == 2 and e[0] in hardware_cfg['nodes'] and e[1] in hardware_cfg['nodes']
        e = tuple(sorted(e))
        bw_edges[e] = {"bw": v, "f": 0}
    for dag_i, dag in enumerate(use_cases):
        for k, v in dag.edges.items():
            ip_ip = tuple(sorted([dag.nodes[k[0]]['phy_node'], dag.nodes[k[1]]['phy_node']]))
            bw_edges[ip_ip]["f"] += v["total"]
            v["bw"] = bw_edges[ip_ip]["bw"]
            interface += v["INTF"]
            memory += v["DRAM"]

        for k, v in dag.nodes.items():
            total = sum([dag.edges[(i, k)]["total"] for i in dag.predecessors(k)])
            if v["performance"] is None or total == 0:
                continue
            throughput.append(
                {"v": v["performance"] * v["partition"] / total, "name": f"compute:{v['phy_node']}({dag_i}-{k})"})

    for k, v in bw_edges.items():
        throughput.append({"v": v["bw"] / v["f"], "name": f"BW:{k[0]}-{k[1]}"})

    throughput.append({"v": hardware_cfg["interface"] / interface, "name": f"BW:interface"})
    throughput.append({"v": hardware_cfg["memory"] / memory, "name": f"BW:memory"})
    throughput.sort(key=lambda x: x['v'])

    if print_tag:
        print(f"throughput:\t{throughput[0]['v']}\n")
        for i in throughput:
            print(f"%-20s\t\t{i['v']}" % i['name'])
        print("")
        for dag_i, dag in enumerate(use_cases):
            print(f"use case {dag_i}:\t{throughput[0]['v'] * dag.graph['weight']}")
        print("\n\n")
    return throughput[0]['v']


def calc_mm1n(rho, N: int) -> float:
    if rho == 1:
        return (N - 1) / 2
    try:
        return rho / (1 - rho) - N / (rho ** -N - 1)
    except (OverflowError, ZeroDivisionError):
        return rho / (1 - rho)


def calc_latency(hardware_cfg, dags, print_tag=False):
    for dag in dags:
        for k, v in dag.nodes.items():
            if v['performance'] is None:
                v['q_lat'] = 0.0
                v['lat'] = 0.0
                continue
            total = sum([dag.edges[(i, k)]["total"] for i in dag.predecessors(k)])
            rho = dag.in_degree(k) * dag.graph['bandwidth-in'] * total / (v['performance'] * v['partition'])
            lat = dag.graph['g_in'] * total * v['Q_num'] / v['performance']
            v['q_lat'] = calc_mm1n(rho, v['Q_len']) * lat
            v['lat'] = v['q_lat'] + lat + v['overhead']

    latency = 0
    for dag in dags:
        for k, v in dag.edges.items():
            v['lat'] = dag.nodes[k[0]]['lat'] + dag.graph['g_in'] * (v['INTF'] / hardware_cfg['interface'] +
                                                                     v['DRAM'] / hardware_cfg['memory'])
        longest_path = nx.dag_longest_path(dag, 'lat')
        lat = nx.dag_longest_path_length(dag, 'lat')
        latency += lat
        if print_tag:
            print(longest_path)
            print(f"latency {lat * 10 ** 6} us")

    return latency / len(dags)


def run_model(graph, model_range, bw_lat, no_lat=False, log_scale=False):
    config = read_config(graph)
    use_cases = create_dags(config["software"])
    throughput = calc_throughput(config["hardware"], use_cases, True)
    if no_lat:
        return
    bw, lat = [], []
    for i in range(model_range):
        bw.append(throughput * i / 100)
        use_cases[0].graph['bandwidth-in'] = bw[-1]
        lat.append(calc_latency(config["hardware"], use_cases, i == 0 or i == model_range - 1) * 1E6)
    plt.plot(bw, lat)
    if bw_lat is None:
        plt.show()
        return
    show_data((bw_lat,))

    for i, j in to_log_scale(*bw_lat) if log_scale else zip(*bw_lat):
        use_cases[0].graph['bandwidth-in'] = i
        latency = calc_latency(config["hardware"], use_cases)
        print(i, j, latency * 1E6)

    # nx.draw(use_cases[0], pos=nx.spring_layout(use_cases[0]), with_labels=True)
    # plt.show()


if __name__ == '__main__':
    # run_model("graphs/v2/NVMe-oF/4KB-random read.yml", 90, "data/NVMe-oF/4KB-randread.txt", 128)
    # run_model("graphs/v2/NVMe-oF/8KB-random read.yml", 97, "data/NVMe-oF/8KB-randread.txt", 128, log_scale=True)
    # run_model("graphs/v2/NVMe-oF/128KB-random read.yml", 95, "data/NVMe-oF/128KB-randread.txt", 8)
    # run_model('graphs/v2/NVMe-oF/4KB-sequential write.yml', 100, "data/NVMe-oF/4KB-seqwrite.txt", 9)
    # run_model('graphs/v2/NVMe-oF/4KB-rwmixed.yml', 100, None, True)
    # run_model("graphs/v2/SSD/4KB-parallel.yml", 90, read_ssd_data("data/SSD/4KB-randread.txt", data_range=128),
    #           log_scale=True)
    # run_model("graphs/v2/SSD/4KB-serial.yml", 90, read_ssd_data("data/SSD/4KB-randread.txt", data_range=128),
    #           log_scale=True)
    # run_model('graphs/v2/LEED/get-1KB-4SSDs.yml', 96, read_leed_data("data/LEED/1KB-get.txt", 1024, data_range=10))
    # run_model('graphs/v2/LEED/get-256B-4SSDs.yml', 95, read_leed_data("data/LEED/256B-get.txt", 256, data_range=10))
    # run_model('graphs/v2/LEED/set-1KB-4SSDs.yml', 99, read_leed_data("data/LEED/1KB-set.txt", 1024, data_range=10))
    # run_model('graphs/v2/LEED/set-256B-4SSDs.yml', 98, read_leed_data("data/LEED/256B-set.txt", 256, data_range=10))
    # run_model('graphs/v2/LEED/del-1KB-4SSDs.yml', 97, read_leed_data("data/LEED/1KB-del.txt", 1024, data_range=10))
    # run_model('graphs/v2/LEED/del-256B-4SSDs.yml', 97, read_leed_data("data/LEED/256B-del.txt", 256, data_range=10))
    run_model('graphs/v2/LEED/get&set-256B-4SSDs.yml', 100, None, True)
    pass
