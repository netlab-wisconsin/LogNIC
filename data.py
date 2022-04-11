import re
import matplotlib.pyplot as plt


def select_data_range(func):
    def wrapper(*args, data_range=None, **kwargs):
        bw, lat = func(*args, **kwargs)
        data_range = data_range or len(bw)
        return bw[:data_range], lat[:data_range]

    return wrapper


@select_data_range
def read_ssd_data(path):
    with open(path) as f:
        log = f.read()
    bw = list(re.findall(r"bw \(  ([KM])iB/s\):.+ avg=([0-9.]+)", log))
    bw = [float(i[1]) / (1024 * 1024 if i[0] == 'K' else 1024) for i in bw]
    lat = re.findall(r" lat \(([un])sec\):.+avg= *([0-9.]+)", log)
    lat = [float(i[1]) / (1024 if i[0] == 'n' else 1) for i in lat]
    return bw, lat


@select_data_range
def read_leed_data(path, granularity):
    average_latency = []
    throughput = []
    with open(path) as f:
        for i in f.readlines():
            if i.startswith("average latency"):
                average_latency.append(float(i.split()[-2]))
            elif i.startswith("TRANSACTION rate"):
                throughput.append(float(i.split()[-1]) * granularity / (1 << 30))
    return throughput, average_latency


# [(bw,lat),]
def show_data(data):
    for bw, lat in data:
        plt.plot(bw, lat)
    plt.show()


def to_log_scale(bw, lat):
    i = 1
    while i <= len(bw):
        yield bw[i - 1], lat[i - 1]
        i <<= 1


if __name__ == '__main__':
    # show_data(["data/SSD/4KB-randread.txt", "data/NVMe-oF/4KB-randread.txt"], (128, 150))
    # show_data(["data/NVMe-oF/8KB-randread.txt", "data/NVMe-oF/8KB-randread-2.txt"], (128, 128))
    # show_data([read_ssd_data("data/SSD/512B-randread.txt")])
    # show_data(["data/SSD/1KB-seqwrite.txt", "data/SSD/512B-seqwrite.txt"], (32, 32))
    # show_data(["data/SSD/8KB-seqwrite.txt"], (5,))
    # print(to_log_scale("data/SSD/4KB-randread.txt", None))
    # show_data([read_leed_data("data/LEED/1KB-get.txt", 1024, data_range=10)])
    show_data([read_leed_data("data/LEED/1KB-set.txt", 1024, data_range=10)])
    # show_data([read_leed_data("data/LEED/256B-set.txt", 256, data_range=10)])
