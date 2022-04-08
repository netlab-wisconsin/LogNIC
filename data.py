import re
import matplotlib.pyplot as plt


def read_ssd_data(path):
    with open(path) as f:
        log = f.read()
    bw = list(re.findall(r"bw \(  ([KM])iB/s\):.+ avg=([0-9.]+)", log))
    bw = [float(i[1]) / (1024 * 1024 if i[0] == 'K' else 1024) for i in bw]
    lat = re.findall(r" lat \(([un])sec\):.+avg= *([0-9.]+)", log)
    lat = [float(i[1]) / (1024 if i[0] == 'n' else 1) for i in lat]
    return bw, lat


def show_data(paths, ranges):
    for i, j in zip(paths, ranges):
        bw, lat = read_ssd_data(i)
        plt.plot(bw[:j], lat[:j])
    plt.show()


def to_log_scale(path, data_range=None):
    bw, lat = read_ssd_data(path)
    data_range = data_range or len(bw)
    i = 1
    res = []
    while i <= data_range:
        res.append((bw[i - 1], lat[i - 1]))
        i <<= 1
    return res


if __name__ == '__main__':
    # show_data(["data/SSD/4KB-randread.txt", "data/NVMe-oF/4KB-randread.txt"], (128, 150))
    show_data(["data/NVMe-oF/8KB-randread.txt", "data/NVMe-oF/8KB-randread-2.txt"], (128, 128))
    # show_data(["data/SSD/8KB-seqwrite.txt"], (5,))
    # print(to_log_scale("data/SSD/4KB-randread.txt", None))
