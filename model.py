import networkx as nx
import yaml
import itertools
import math
from scipy.stats import poisson
import matplotlib.pyplot as plt

with open("graphs/v1/1.yml") as f:
    config = yaml.safe_load(f)

DAG = nx.DiGraph()
MDG = nx.MultiDiGraph()

node_ids = itertools.count(1, 1)


def create_dag(path, prev_node=None, last_node=None):
    for i in path:
        if isinstance(i, list):
            for p in i:
                last_node = create_dag(p, prev_node, last_node)
            prev_node = last_node
            last_node = None
            continue
        assert i["u"] in config["nodes"]
        assert i["v"] in config["nodes"]
        if prev_node is None:
            prev_node = next(node_ids)
            DAG.add_node(prev_node, name=i["u"], **config["nodes"][i["u"]])
        assert i["u"] == DAG.nodes[prev_node]["name"]
        if i is path[-1] and last_node is not None:
            assert DAG.nodes[last_node]["name"] == i["v"]
            node_id = last_node
        else:
            node_id = next(node_ids)
            DAG.add_node(node_id, name=i["v"], **config["nodes"][i["v"]])
        DAG.add_edge(prev_node, node_id, f=i["f"], g=i["g"])
        prev_node = node_id
    return prev_node


def create_mdg():
    MDG.add_nodes_from(config["nodes"].items())
    for i in DAG.edges:
        edge = node_name[i[0]], node_name[i[1]]
        MDG.add_edge(*edge, **DAG[i[0]][i[1]])
    for k, v in MDG.nodes.items():
        v['TC'] = v['A'] * sum((j['f'] for i in MDG.predecessors(k) for j in MDG[i][k].values())) / v['P']
        v['TD'] = sum((j['g'] for i in MDG.predecessors(k) for j in MDG[i][k].values()))
        if v['S']:
            v['TD'] += sum((j['g'] for i in MDG.successors(k) for j in MDG[k][i].values()))
        v['TD'] *= v['B']


def calc_throughput():
    latencies = {k: {'TC': v['TC'], 'TD': v['TD']} for k, v in MDG.nodes.items()}
    bottle_neck = max(MDG.nodes, key=lambda x: max(MDG.nodes[x]['TC'], MDG.nodes[x]['TD']))
    MDG.graph['TS'] = max(latencies[bottle_neck].values())
    print(latencies)
    print(bottle_neck, latencies[bottle_neck])
    print(f"throughput {config['pkt_size'] / MDG.graph['TS']} MB/s")


def calc_md1n(rho, T, N: int) -> float:
    alpha = []
    i_max = 0
    for i_max in range(N):
        alpha.append(poisson.pmf(k=i_max, mu=rho))
        if alpha[-1] == 0.0:
            break
    a = [1, math.exp(rho) - 1]
    for n in range(2, N + 1):
        tmp = a[-1] - sum((alpha[i] * a[n - i] for i in range(1, min(n, i_max)))) - alpha[min(n - 1, i_max)]
        a.append(math.exp(rho) * tmp)
    b = [a[0]]
    for k in range(1, N + 1):
        b.append(b[-1] + a[k])
    return T * (N - 1 - (sum((b[k] for k in range(N))) - N) / (rho * b[N - 1]))


def calc_mm1n(rho, mu, N: int) -> float:
    if rho == 1:
        return (N - 1) / 2 / mu
    return (rho / (1 - rho) - N * rho ** N / (1 - rho ** N)) / mu


def calc_latency():
    for v in MDG.nodes.values():
        rho = v['TD'] / MDG.graph['TS']
        b = v['B'] * config['block_size'] / (1 << 20)
        n = round(v['N'] / config['block_size']) + 1
        v['TQ'] = calc_md1n(rho, b, n)

    for k, v in DAG.edges.items():
        b = max(DAG.nodes[k[0]]['B'], DAG.nodes[k[1]]['B'])
        tq = MDG.nodes[node_name[k[1]]]['TQ']
        v['T'] = tq + v['f'] * DAG.nodes[k[1]]['A'] + v['g'] * b
    longest_path = nx.dag_longest_path(DAG, 'T')
    print([node_name[i] for i in longest_path])
    print([DAG[longest_path[i]][longest_path[i + 1]]['T'] for i in range(len(longest_path) - 1)])
    print(f"latency {nx.dag_longest_path_length(DAG, 'T') * 10 ** 6} us")


create_dag(config["path"])
node_name = nx.get_node_attributes(DAG, 'name')
create_mdg()
calc_throughput()
calc_latency()
# nx.draw(DAG, pos=nx.spring_layout(DAG), labels=node_name)
# plt.show()
# nx.draw(MDG, pos=nx.spring_layout(MDG), with_labels=True)
# plt.show()
plt.plot([calc_mm1n(i / 100, 1, 10) for i in range(1, 200)])
plt.plot([calc_mm1n(i / 100, 1, 1000) for i in range(1, 200)])
plt.show()
# pass