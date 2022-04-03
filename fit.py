from model_v2 import read_config, create_dag, calc_latency
import re
import matplotlib.pyplot as plt
import networkx as nx
from scipy.optimize import curve_fit


def read_ssd_data(path):
    with open(path) as f:
        log = f.read()
    bw = list(re.findall(r"  read :.+, bw=([0-9.]+[KM])B/s", log))
    bw = [float(i[:-1]) / (1024 * 1024 if i[-1] == 'K' else 1024) for i in bw]
    lat = list(map(float, re.findall(r" {5}lat \(usec\): .+ avg=([0-9.]+)", log)))
    return bw, lat


dag = nx.DiGraph()


def func(x, Q_num, Q_len, overhead):
    # overhead = 65e-6
    dag.nodes['IP'].update(
        {'overhead': overhead * 1e-6, 'Q_num': Q_num, 'Q_len': Q_len})
    res = []
    for i in x:
        dag.graph['bandwidth-in'] = i
        res.append(calc_latency([dag]) * 1E6)
    return res


def main():
    bw, lat = read_ssd_data("data/SSD-4KB-read.txt")
    bw, lat = bw[:32], lat[:32]

    config = read_config("graphs/v2/single-ip.yml")
    global dag
    dag = create_dag(config['software'][0])
    dag.nodes['IP']['performance'] = max(bw)
    arg, _ = curve_fit(func, bw, lat)
    print(arg)
    plt.plot(bw, lat)
    plt.plot(bw, func(bw, *arg))
    plt.show()


if __name__ == '__main__':
    main()
