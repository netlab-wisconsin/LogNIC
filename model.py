import networkx as nx
import yaml
import matplotlib.pyplot as plt
from numpy import seterr
import numpy as np
from data import *

seterr(all='ignore')


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
            dag.add_edge(e[0], e[1], **v)
        dag.graph['g_in'] = dag.graph['granularity-in'] / float(1 << 30)
        dag.graph['weight'] = w
        dags.append(dag)
    return dags


def calc_throughput(hardware_cfg, use_cases, print_tag=False, return_all=False):
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
            bw_edges[ip_ip]["f"] += v["total"] * dag.graph['weight']
            v["bw"] = bw_edges[ip_ip]["bw"]
            interface += v["INTF"] * dag.graph['weight']
            memory += v["DRAM"] * dag.graph['weight']

        for k, v in dag.nodes.items():
            total = sum([dag.edges[(i, k)]["total"] for i in dag.predecessors(k)])
            if v["performance"] is None or total == 0:
                continue
            throughput.append({"v": v["performance"] * v["partition"] / total / dag.graph['weight'],
                               "name": f"compute:{v['phy_node']}({dag_i}-{k})"})

    for k, v in bw_edges.items():
        throughput.append({"v": v["bw"] / v["f"], "name": f"BW:{k[0]}-{k[1]}"})
    if interface != 0:
        throughput.append({"v": hardware_cfg["interface"] / interface, "name": f"BW:interface"})
    if memory != 0:
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
    return throughput if return_all else throughput[0]['v']


def calc_mm1n(rho, N: int) -> float:
    if rho == 1:
        return (N - 1) / 2
    rho = np.array([rho])
    return (rho / (1 - rho) - N / (rho ** -N - 1))[0]


def calc_pn(rho, N: int) -> float:
    if rho == 1:
        return 1 / (N + 1)
    rho = np.array([rho])
    return ((1 - rho) / (rho ** -N - rho))[0]


def calc_real_throughput(hardware_cfg, use_cases):
    bw = calc_throughput(hardware_cfg, use_cases, return_all=True)
    bw_in = sum((i.graph['bandwidth-in'] for i in use_cases))
    ret = 0
    for u_i, u in enumerate(use_cases):
        for i in bw:
            match = re.search(r"\(([0-9]+)-(.+)\)", i['name'])
            if match and int(match.groups()[0]) == u_i:
                node = match.groups()[1]
                ret += u.graph['bandwidth-in'] * (1 - calc_pn(bw_in / i['v'], u.nodes[node]['Q_len']))
                break
    if bw[0]['name'].startswith('BW:') and ret > bw[0]['v']:
        return bw[0]['v']
    return ret
    # if bw[0]['name'].startswith('BW:'):
    #     return bw_in
    # else:
    #     use_case, node = re.search(r"\(([0-9]+)-(.+)\)", bw[0]['name']).groups()
    #     if bw[0]['v'] == 0:
    #         return 0
    #     return bw_in * (1 - calc_pn(bw_in / bw[0]['v'], use_cases[int(use_case)].nodes[node]['Q_len']))


def calc_latency(hardware_cfg, dags, print_tag=False, return_all=False):
    for dag in dags:
        for k, v in dag.nodes.items():
            if v['performance'] is None:
                v['q_lat'] = 0.0
                v['lat'] = 0.0
                continue
            total = sum([dag.edges[(i, k)]["total"] for i in dag.predecessors(k)])
            if v['partition'] == 0:
                v['q_lat'] = 1.0
                v['lat'] = 1.0
                continue
            rho = dag.graph['bandwidth-in'] * total / (v['performance'] * v['partition'])
            lat = dag.graph['g_in'] * total * v['Q_num'] / v['performance'] / dag.in_degree(k)
            v['q_lat'] = calc_mm1n(rho, v['Q_len']) * lat
            v['lat'] = v['q_lat'] + lat + v['overhead']

    latency, latencies = 0, []
    for dag in dags:
        for k, v in dag.edges.items():
            v['lat'] = dag.nodes[k[0]]['lat'] + dag.graph['g_in'] * (v['INTF'] / hardware_cfg['interface'] +
                                                                     v['DRAM'] / hardware_cfg['memory'])
        longest_path = nx.dag_longest_path(dag, 'lat')
        lat = nx.dag_longest_path_length(dag, 'lat')
        latency += lat * dag.graph['weight']
        latencies.append(lat)
        if print_tag:
            print(longest_path)
            print(f"latency {lat * 10 ** 6} us")

    return latencies if return_all else latency


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
        latency = calc_latency(config["hardware"], use_cases, return_all=True)[0]
        print(i, j, latency * 1E6)
    # nx.draw(use_cases[0], pos=nx.spring_layout(use_cases[0]), with_labels=True)
    # plt.show()


if __name__ == '__main__':
    # run_model("graphs/NVMe-oF/4KB-random read.yml", 90, read_ssd_data("data/NVMe-oF/4KB-randread.txt", data_range=128))
    # run_model("graphs/NVMe-oF/8KB-random read.yml", 97, read_ssd_data("data/NVMe-oF/8KB-randread.txt", data_range=128), log_scale=True)
    # run_model("graphs/NVMe-oF/128KB-random read.yml", 95, read_ssd_data("data/NVMe-oF/128KB-randread.txt", data_range=8))
    # run_model('graphs/NVMe-oF/4KB-sequential write.yml', 100, read_ssd_data("data/NVMe-oF/4KB-seqwrite.txt", data_range=9))
    # run_model('graphs/NVMe-oF/4KB-rwmixed.yml', 100, None, True)
    # run_model("graphs/SSD/4KB-parallel.yml", 90, read_ssd_data("data/SSD/4KB-randread.txt", data_range=128),
    #           log_scale=True)
    # run_model("graphs/SSD/4KB-serial.yml", 90, read_ssd_data("data/SSD/4KB-randread.txt", data_range=128),
    #           log_scale=True)
    # run_model('graphs/LEED/get-1KB-4SSDs.yml', 96, read_leed_data("data/LEED/1KB-get.txt", 1024, data_range=10))
    # run_model('graphs/LEED/get-256B-4SSDs.yml', 95, read_leed_data("data/LEED/256B-get.txt", 256, data_range=10))
    run_model('graphs/LEED/set-1KB-4SSDs.yml', 98, read_leed_data("data/LEED/1KB-set.txt", 1024, data_range=10))
    # run_model('graphs/LEED/set-256B-4SSDs.yml', 98, read_leed_data("data/LEED/256B-set.txt", 256, data_range=10))
    # run_model('graphs/LEED/del-1KB-4SSDs.yml', 97, read_leed_data("data/LEED/1KB-del.txt", 1024, data_range=10))
    # run_model('graphs/LEED/del-256B-4SSDs.yml', 97, read_leed_data("data/LEED/256B-del.txt", 256, data_range=10))
    # run_model('graphs/LEED/get&set-256B-4SSDs.yml', 100, None, True)
    # run_model('graphs/switch/1.yml', 150, None)

    # for j in (1, 2, 4, 8, 16):
    #     plt.plot([calc_pn(i / 100.0, j) for i in range(100)])
    # plt.show()