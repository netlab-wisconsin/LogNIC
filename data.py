import re


def read_ssd_data(path):
    with open(path) as f:
        log = f.read()
    bw = list(re.findall(r"bw \(  ([KM])iB/s\):.+ avg=([0-9.]+)", log))
    bw = [float(i[1]) / (1024 * 1024 if i[0] == 'K' else 1024) for i in bw]
    lat = re.findall(r" lat \(([un])sec\):.+avg= *([0-9.]+)", log)
    lat = [float(i[1]) / (1024 if i[0] == 'n' else 1) for i in lat]
    return bw, lat
