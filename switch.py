from data import read_ssd_data
from model_v2 import read_config, create_dags, calc_latency, calc_real_throughput
import matplotlib.pyplot as plt
import networkx as nx
from scipy.optimize import curve_fit
import numpy as np


def fit():
    def func(x, Q_num, Q_len):
        config = read_config('graphs/v2/switch/1.yml')
        config["software"][0]['nodes']['stage3'].update({'Q_num': Q_num, 'Q_len': Q_len})
        config["software"][1]['nodes']['stage3'].update({'Q_num': Q_num, 'Q_len': Q_len})
        # config["software"][0]['edges']['ingress-stage3']['partition'] = Q_len
        # config["software"][1]['edges']['ingress-stage3']['partition'] = Q_len

        latencies = []
        for i in x:
            config["software"][0]['bandwidth-in'] = i[0] / 8.0
            config["software"][1]['bandwidth-in'] = i[1] / 8.0
            use_cases = create_dags(config["software"])
            partition = np.array(i)
            partition = partition / np.sum(partition)
            use_cases[0].nodes['stage3']['partition'] = partition[0]
            use_cases[1].nodes['stage3']['partition'] = partition[1]
            latencies.append(calc_latency(config['hardware'], use_cases) * 1e9)
        return latencies

    xs, ys = [], []
    with open("data/switch/SwitchML.txt") as f:
        for line in f.readlines():
            d = list(map(float, line.split()))
            xs.append(d[:2])
            ys.append((d[-2] * d[0] + d[-1] * d[1]) / (d[0] + d[1]))
    # print(xs, ys)
    data_range = 11
    arg, _ = curve_fit(func, xs[:data_range], ys[:data_range], bounds=((0, 1), (np.inf, np.inf)))
    print(*arg[::-1])
    print(func(xs[:data_range], *arg))
    x_sum = list(map(sum, xs[:data_range]))
    plt.plot(x_sum, ys[:data_range])
    plt.plot(x_sum, func(xs[:data_range], *arg))
    plt.show()
    return arg


def switch(Q_num=None, Q_len=None):
    def func(x):
        use_cases[0].nodes['stage3']['partition'] = x[0]
        use_cases[1].nodes['stage3']['partition'] = x[1]
        return -calc_real_throughput(config['hardware'], use_cases)

    # for i in range(10, 110, 10):
    with open("data/switch/SwitchML.txt") as f:
        for line in f.readlines():
            d = list(map(float, line.split()))
            config = read_config('graphs/v2/switch/1.yml')
            if Q_num is not None:
                config["software"][0]['nodes']['stage3'].update({'Q_num': Q_num, 'Q_len': Q_len})
                config["software"][1]['nodes']['stage3'].update({'Q_num': Q_num, 'Q_len': Q_len})
            config["software"][0]['bandwidth-in'] = d[0] / 8.0
            config["software"][1]['bandwidth-in'] = d[1] / 8.0
            use_cases = create_dags(config["software"])
            # res = minimize(func, np.array((0.5, 0.5)), bounds=((0, None), (0, None)),
            #                constraints={'type': "eq", 'fun': lambda x: x[0] + x[1] - 1})['x']

            res = np.array(d[2:4])
            res = res / np.sum(res)
            func(res)
            # print(res, -func(res))
            latencies = calc_latency(config['hardware'], use_cases, return_all=True)
            print(latencies[0] * 1e9, latencies[1] * 1e9)


if __name__ == '__main__':
    # switch(*fit())
    switch()
