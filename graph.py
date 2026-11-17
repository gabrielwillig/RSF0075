import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from topology_utils import render_graph, run_interactive_cli


def parse_graph_file(file_path: Path) -> nx.Graph:
    graph = nx.Graph()
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) != 3:
                raise ValueError(
                    f"Malformed line {line_num}: expected 'SRC DST WEIGHT', got '{raw_line.strip()}'"
                )

            u, v, weight_str = parts
            try:
                weight = float(weight_str)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid weight '{weight_str}' at line {line_num}."
                ) from exc

            graph.add_edge(u, v, weight=weight)

    return graph


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize graph topology and compute shortest paths interactively."
    )
    parser.add_argument(
        "file",
        type=Path,
        nargs="?",
        default=Path("example.txt"),
        help="Path to graph definition file (default: example.txt)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    try:
        graph = parse_graph_file(args.file)
    except (FileNotFoundError, ValueError) as err:
        print(f"[Error] {err}", file=sys.stderr)
        sys.exit(1)

    if graph.number_of_nodes() == 0:
        print("[Error] Graph contains no nodes. Exiting.", file=sys.stderr)
        sys.exit(1)

    layout = nx.spring_layout(graph, seed=42)

    plt.ion()
    render_graph(graph, layout)

    print(
        f"\nLoaded {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges from '{args.file}'."
    )

    try:
        run_interactive_cli(graph, layout)
    finally:
        plt.close("all")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nOperation cancelled by user (Ctrl+C). Exiting.")
        sys.exit(0)
