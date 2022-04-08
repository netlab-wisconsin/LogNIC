from data import read_ssd_data
from model_v2 import read_config, create_dags, calc_latency
import matplotlib.pyplot as plt
import networkx as nx
from scipy.optimize import curve_fit
import numpy as np

dag = nx.DiGraph()


def func(x, performance, Q_num, Q_len, overhead):
    dag.nodes['IP'].update({'performance': performance, 'overhead': overhead * 1e-6, 'Q_num': Q_num, 'Q_len': Q_len})
    res = []
    for i in x:
        dag.graph['bandwidth-in'] = i
        res.append(calc_latency([dag]) * 1E6)
    return res


def main():
    data_range = 6
    bw, lat = read_ssd_data("data/SSD/128KB-randread.txt")
    config = read_config("graphs/v2/single-ip.yml")
    global dag
    dag = create_dags(config['software'])[0]
    arg, _ = curve_fit(func, bw[:data_range], lat[:data_range], bounds=((0, 0, 1, 0), (np.inf, np.inf, np.inf, np.inf)))
    print("performance(GB/s) Q_num Q_len overhead(us)")
    print(*arg)
    print(func([2.5], *arg))
    plt.plot(bw[:8], lat[:8])
    bw = [arg[0] * i / 100 for i in range(97)]
    plt.plot(bw, func(bw, *arg))
    plt.show()


if __name__ == '__main__':
    main()
