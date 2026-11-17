# Wireless Networks - RSF0075 (3a fase 2026 - CPGEI)

Topology visualization, shortest-path routing, and distributed Link-State discovery simulator developed for **Redes sem fio - RSF0075 (3a fase 2026 - CPGEI)**.

## Modules

- `network_discovery.py`: Generates a connected random wireless topology with $N$ nodes (`weight = 1`), simulates distributed `HELLO` neighbor discovery and `LSA` topology flooding across independent `WirelessNode` instances, prints control message logs and per-node routing tables, and provides an interactive Matplotlib route inspector.
- `graph.py`: Loads an undirected weighted topology from a text file (`SRC DST WEIGHT`), renders it with Matplotlib, and provides an interactive shortest-path CLI.
- `topology_utils.py`: Shared graph sorting, shortest-path computation, non-blocking Matplotlib rendering, and interactive CLI utilities.

## Running with `uv`

Run the distributed Link-State discovery simulator (passing $N$ or entering it interactively):

```bash
uv run network_discovery.py 6
```

Optional flags: `--origin <node_id>` to highlight a specific node's discovery log and `--seed <int>` for reproducible topologies.

Run the file-based topology viewer and shortest-path calculator:

```bash
uv run graph.py example.txt
```
