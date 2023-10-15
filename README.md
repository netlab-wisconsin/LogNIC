# LogNIC

LogNIC systematically analyzes the performance characteristics of a SmartNIC-offloaded program. Unlike conventional execution flow-based modeling, LogNIC employs a packet-centric approach that examines SmartNIC execution based on how packets traverse heterogeneous computing domains, on-/off-chip interconnects, and memory subsystems. It abstracts away the low-level device details, represents a deployed program as an execution graph, retains a handful of configurable parameters, and generates latency/throughput estimation for a given traffic profile. It further exposes a couple of extensions to handle multi-tenancy, traffic interleaving, and accelerator peculiarity. LogNIC can estimate performance bounds, explore software optimization strategies, and provide guidelines for new hardware designs.

## Installation

    pip install -r requirements.txt

## Run

TODO
