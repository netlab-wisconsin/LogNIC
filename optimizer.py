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


if __name__ == '__main__':
    rw_mixed()
