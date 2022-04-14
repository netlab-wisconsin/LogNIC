from model_v2 import *
from scipy.optimize import minimize
import numpy as np


def rw_mixed():
    def func(x, print_tag=False):
        use_cases[0].nodes['SSD']['partition'] = x[0]
        use_cases[1].nodes['SSD']['partition'] = x[1]
        return -calc_throughput(config["hardware"], use_cases, print_tag)

    for i in range(1, 10):
        config = read_config('graphs/v2/NVMe-oF/4KB-rwmixed.yml')
        config["software"][0]['bandwidth-in'] = 1 - i / 10.0
        config["software"][1]['bandwidth-in'] = i / 10.0
        use_cases = create_dags(config["software"])
        res = minimize(func, np.array((0.5, 0.5)), bounds=((0, None), (0, None)),
                       constraints={'type': "eq", 'fun': lambda x: x[0] + x[1] - 1})['x']
        print(f"{100 - i * 10}% read: gamma {res}")
        func(res, True)


def get_set_mixed():
    def create_graph(x):
        for j in range(4):
            use_cases[0].nodes[f"SSD{j}_0"]['partition'] = x[0]
            use_cases[0].nodes[f"SSD{j}_1"]['partition'] = x[1]
            use_cases[1].nodes[f"SSD{j}_0"]['partition'] = x[2]
            use_cases[1].nodes[f"SSD{j}_1"]['partition'] = x[3]
            use_cases[1].nodes[f"SSD{j}_2"]['partition'] = x[4]
        return config["hardware"], use_cases

    for i in range(0, 11):
        config = read_config('graphs/v2/LEED/get&set-1KB-4SSDs.yml')
        config["software"][0]['bandwidth-in'] = 1 - i / 10.0
        config["software"][1]['bandwidth-in'] = i / 10.0
        use_cases = create_dags(config["software"])
        x0 = np.random.random(5)
        x0 = x0 / np.sum(x0)
        res = minimize(lambda x: - calc_throughput(*create_graph(x)), x0, bounds=[(0, None)] * 5,
                       constraints={'type': "eq", 'fun': lambda x: sum(x) - 1})['x']
        print(f"{100 - i * 10}% read: gamma ", *res)
        throughput = calc_throughput(*create_graph(res))
        print((1 - i / 10.0) * throughput, i / 10.0 * throughput)


LEED_CONFIG = {
    "set-1KB": {"max_throughput": 0.6183814944660193, "partition_num": 3},
    "set-256B": {"max_throughput": 0.174570798097404, "partition_num": 3},
    "get-1KB": {"max_throughput": 0.954875698868065, "partition_num": 2},
    "get-256B": {"max_throughput": 0.238858411135757, "partition_num": 2},
    "del-1KB": {"max_throughput": 0.755765818447113, "partition_num": 2},
    "del-256B": {"max_throughput": 0.18812962077641487, "partition_num": 2},
}


def leed_operation(op, percentage=0.3, max_lat=None):
    def create_graph(x):
        config["software"][0]['bandwidth-in'] = x[0]
        dags = create_dags(config["software"])
        # x[-3], x[-2], x[-1] = 0.3654264723, 0.317298835, 0.3172746927
        for i in range(4):
            for j in range(LEED_CONFIG[op]["partition_num"]):
                dags[0].nodes[f"SSD{i}_{j}"]['partition'] = x[1 + j]
        return config["hardware"], dags

    config = read_config(f'graphs/v2/LEED/{op}-4SSDs.yml')
    partition = np.random.random(LEED_CONFIG[op]["partition_num"])
    partition /= np.sum(partition)
    x0 = np.concatenate(([0.0], partition))
    bounds = [(0, None)] * x0.shape[0]
    constraints = [{'type': "eq", 'fun': lambda x: 1 - sum(x[1:])}]
    if max_lat:
        constraints.append({'type': "eq", 'fun': lambda x: max_lat - calc_latency(*create_graph(x)) * 1e6})
        res = minimize(lambda x: - calc_real_throughput(*create_graph(x)), x0, method='SLSQP', bounds=bounds,
                       constraints=constraints)['x']
    else:
        throughput_bound = LEED_CONFIG[op]["max_throughput"] * percentage
        constraints.append({'type': "eq", 'fun': lambda x: throughput_bound - calc_real_throughput(*create_graph(x))})
        res = minimize(lambda x: calc_latency(*create_graph(x)) * 1e6, x0, method='SLSQP', bounds=bounds,
                       constraints=constraints)['x']
    print(*res)
    hardware_cfg, use_cases = create_graph(res)
    print(calc_real_throughput(hardware_cfg, use_cases), calc_latency(hardware_cfg, use_cases) * 1e6)


if __name__ == '__main__':
    # rw_mixed()
    # get_set_mixed()
    # leed_operation('set-1KB', percentage=0.50)
    # leed_operation('set-1KB', max_lat=110)
    # leed_operation('get-1KB', percentage=0.30)
    # leed_operation('get-1KB', max_lat=200)
    leed_operation('del-256B', percentage=0.80)
    leed_operation('del-256B', max_lat=120)
