from model_v2 import read_config, create_dag, calc_latency
import re
import matplotlib.pyplot as plt
import networkx as nx
from scipy.optimize import curve_fit
import numpy as np


def read_ssd_data(path):
    with open(path) as f:
        log = f.read()
    bw = list(re.findall(r"bw \(  ([KM])iB/s\):.+ avg=([0-9.]+)", log))
    bw = [float(i[1]) / (1024 * 1024 if i[0] == 'K' else 1024) for i in bw]
    lat = re.findall(r" lat \(([un])sec\):.+avg= *([0-9.]+)", log)
    lat = [float(i[1]) / (1024 if i[0] == 'n' else 1) for i in lat]
    return bw, lat


dag = nx.DiGraph()


def func(x, performance, Q_num, Q_len, overhead):
    dag.nodes['IP'].update({'performance': performance, 'overhead': overhead * 1e-6, 'Q_num': Q_num, 'Q_len': Q_len})
    res = []
    for i in x:
        dag.graph['bandwidth-in'] = i
        res.append(calc_latency([dag]) * 1E6)
    return res


def main():
    data_range = 110
    bw, lat = read_ssd_data("data/SSD-4KB-randread.txt")
    config = read_config("graphs/v2/single-ip.yml")
    global dag
    dag = create_dag(config['software'][0])
    arg, _ = curve_fit(func, bw[:data_range], lat[:data_range], bounds=((0, 0, 1, 0), (np.inf, np.inf, np.inf, np.inf)))
    print("performance(GB/s) Q_num Q_len overhead(us)")
    print(*arg)
    plt.plot(bw, lat)
    bw = [arg[0] * i / 100 for i in range(90)]
    plt.plot(bw, func(bw, *arg))
    plt.show()


if __name__ == '__main__':
    main()
