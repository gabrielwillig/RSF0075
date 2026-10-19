import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import networkx as nx


def on_window_close(event) -> None:
    print("\n\nTopology window closed. Exiting application.")
    os._exit(0)


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


def compute_shortest_path(
    graph: nx.Graph, source: str, destination: str
) -> Tuple[List[str], float]:
    path = nx.shortest_path(graph, source=source, target=destination, weight="weight")
    cost = nx.shortest_path_length(
        graph, source=source, target=destination, weight="weight"
    )
    return path, cost


def sort_nodes(nodes: Iterable[str]) -> List[str]:
    def sort_key(item: str) -> Tuple[int, Union[int, str]]:
        if item.isdigit():
            return (0, int(item))
        return (1, item)

    return sorted(nodes, key=sort_key)


def render_graph(
    graph: nx.Graph,
    layout: dict,
    path: Optional[List[str]] = None,
    cost: Optional[float] = None,
) -> None:
    if not plt.fignum_exists(1):
        fig = plt.figure(1, figsize=(8, 6))
    else:
        fig = plt.figure(1)

    if not getattr(fig, "_close_handler_connected", False):
        fig.canvas.mpl_connect("close_event", on_window_close)
        fig._close_handler_connected = True

    plt.clf()
    if fig.canvas.manager:
        fig.canvas.manager.set_window_title("Wireless Network Topology Viewer")

    nx.draw_networkx_nodes(
        graph, layout, node_color="#90CAF9", node_size=700, edgecolors="#1565C0"
    )
    nx.draw_networkx_labels(
        graph, layout, font_size=10, font_family="sans-serif", font_weight="bold"
    )
    nx.draw_networkx_edges(graph, layout, edge_color="#B0BEC5", width=1.8)

    edge_labels = nx.get_edge_attributes(graph, "weight")
    formatted_labels = {
        edge: f"{w:g}" if isinstance(w, float) else str(w)
        for edge, w in edge_labels.items()
    }
    nx.draw_networkx_edge_labels(
        graph, layout, edge_labels=formatted_labels, font_size=9
    )

    if path:
        if len(path) > 1:
            path_edges = list(zip(path[:-1], path[1:]))
            nx.draw_networkx_nodes(
                graph,
                layout,
                nodelist=path,
                node_color="#FF8A65",
                node_size=800,
                edgecolors="#D84315",
            )
            nx.draw_networkx_edges(
                graph, layout, edgelist=path_edges, edge_color="#D84315", width=3.5
            )
            cost_str = f" (Cost: {cost:g})" if cost is not None else ""
            plt.title(
                f"Shortest Path: {' -> '.join(path)}{cost_str}",
                fontsize=12,
                fontweight="bold",
            )
        else:
            nx.draw_networkx_nodes(
                graph,
                layout,
                nodelist=path,
                node_color="#FF8A65",
                node_size=800,
                edgecolors="#D84315",
            )
            plt.title(
                f"Same Source and Destination: Node {path[0]} (Cost: 0)",
                fontsize=12,
                fontweight="bold",
            )
    else:
        plt.title("Input Topology", fontsize=12, fontweight="bold")

    plt.axis("off")
    plt.tight_layout()
    plt.draw()
    plt.pause(0.05)


def prompt_node(
    prompt_label: str,
    available_nodes: List[str],
    allow_cancel: bool = False,
) -> Optional[str]:
    print(f"\nAvailable nodes: {', '.join(available_nodes)}")
    exit_hint = "type 'cancel' or 'c' to abort" if allow_cancel else "type 'exit' or 'q' to quit"
    print(f"({exit_hint})")

    while True:
        if not plt.fignum_exists(1):
            print("\nTopology window closed. Exiting application.")
            sys.exit(0)

        entry = input(f"Enter {prompt_label} node: ").strip()

        if not entry:
            continue

        lower = entry.lower()
        if not allow_cancel and lower in {"exit", "quit", "q"}:
            return None

        if allow_cancel and lower in {"cancel", "c", "back"}:
            return None

        if entry in available_nodes:
            return entry

        print(f"Error: Node '{entry}' does not exist in graph. Try again.")


def run_interactive_cli(graph: nx.Graph, layout: dict) -> None:
    nodes = sort_nodes(graph.nodes())

    while True:
        if not plt.fignum_exists(1):
            print("\nTopology window closed. Exiting application.")
            break

        print("\n" + "-" * 50)
        src = prompt_node(
            prompt_label="source (origin)",
            available_nodes=nodes,
            allow_cancel=False,
        )

        if src is None:
            print("\nExiting application. Goodbye!")
            break

        dst = prompt_node(
            prompt_label="destination",
            available_nodes=nodes,
            allow_cancel=True,
        )

        if dst is None:
            print("Selection cancelled. Returning to origin selection.")
            continue

        try:
            path, cost = compute_shortest_path(graph, src, dst)
            print("\n" + "=" * 40)
            print(f"Shortest Path: {' -> '.join(path)}")
            print(f"Intermediate Nodes: {path[1:-1] if len(path) > 2 else 'None'}")
            print(f"Total Link Cost: {cost:g}")
            print("=" * 40)
            render_graph(graph, layout, path=path, cost=cost)
        except nx.NetworkXNoPath:
            print(f"\n[Result] No path exists between Node '{src}' and Node '{dst}'.")


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