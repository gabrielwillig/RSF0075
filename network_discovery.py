import argparse
import math
import random
import sys
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import matplotlib.pyplot as plt
import networkx as nx

from topology_utils import render_graph, run_interactive_cli, sort_nodes


@dataclass(frozen=True)
class HelloPacket:
    sender_id: str


@dataclass(frozen=True)
class LSAPacket:
    origin_id: str
    seq_num: int
    neighbors: Tuple[str, ...]


@dataclass(frozen=True)
class RoutingEntry:
    destination: str
    next_hop: str
    cost: int
    path: Tuple[str, ...]


@dataclass
class WirelessNode:
    node_id: str
    neighbors: Set[str] = field(default_factory=set)
    local_graph: nx.Graph = field(default_factory=nx.Graph)
    seen_lsa_seqs: Dict[str, int] = field(default_factory=dict)
    routing_table: Dict[str, RoutingEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.local_graph.add_node(self.node_id)

    def receive_hello(self, packet: HelloPacket) -> None:
        self.neighbors.add(packet.sender_id)
        self.local_graph.add_edge(self.node_id, packet.sender_id, weight=1)

    def create_lsa(self, seq_num: int = 1) -> LSAPacket:
        sorted_neighbors = tuple(sort_nodes(self.neighbors))
        self.seen_lsa_seqs[self.node_id] = seq_num
        return LSAPacket(
            origin_id=self.node_id,
            seq_num=seq_num,
            neighbors=sorted_neighbors,
        )

    def receive_lsa(
        self, packet: LSAPacket, from_neighbor: str
    ) -> Tuple[bool, List[str]]:
        if self.seen_lsa_seqs.get(packet.origin_id, 0) >= packet.seq_num:
            return False, []

        self.seen_lsa_seqs[packet.origin_id] = packet.seq_num
        self.local_graph.add_node(packet.origin_id)
        for neighbor in packet.neighbors:
            self.local_graph.add_edge(packet.origin_id, neighbor, weight=1)

        forward_targets = sort_nodes(
            nbr for nbr in self.neighbors if nbr != from_neighbor
        )
        return True, forward_targets

    def compute_routing_table(self) -> None:
        self.routing_table.clear()
        paths = nx.single_source_dijkstra_path(
            self.local_graph, self.node_id, weight="weight"
        )
        for dest in sort_nodes(self.local_graph.nodes()):
            if dest not in paths:
                continue
            path = tuple(paths[dest])
            cost = len(path) - 1
            next_hop = "-" if dest == self.node_id else path[1]
            self.routing_table[dest] = RoutingEntry(
                destination=dest,
                next_hop=next_hop,
                cost=cost,
                path=path,
            )


def generate_connected_topology(
    num_nodes: int, seed: Optional[int] = None
) -> Tuple[nx.Graph, dict]:
    rng = random.Random(seed)
    radius = max(0.35, min(0.9, math.sqrt(2.2 * math.log(num_nodes) / num_nodes)))

    for attempt in range(40):
        attempt_seed = rng.randint(0, 10**9)
        raw_graph = nx.random_geometric_graph(num_nodes, radius, seed=attempt_seed)
        if nx.is_connected(raw_graph):
            mapping = {i: str(i + 1) for i in range(num_nodes)}
            graph = nx.relabel_nodes(raw_graph, mapping)
            layout = {
                str(i + 1): raw_graph.nodes[i]["pos"] for i in range(num_nodes)
            }
            for u, v in graph.edges():
                graph[u][v]["weight"] = 1
            return graph, layout
        radius = min(1.5, radius + 0.05)

    # Fallback: build a random spanning tree and add extra links if RGG did not connect
    graph = nx.Graph()
    node_ids = [str(i + 1) for i in range(num_nodes)]
    graph.add_nodes_from(node_ids)
    for i in range(1, num_nodes):
        parent = str(rng.randint(1, i))
        graph.add_edge(str(i + 1), parent, weight=1)
    layout = nx.spring_layout(graph, seed=seed or 42)
    return graph, layout


def _format_tag(origin_id: str, *involved_ids: str) -> str:
    return "[ORIGIN]" if origin_id in involved_ids else "        "


def simulate_link_state_discovery(
    physical_graph: nx.Graph, origin_id: str
) -> Tuple[Dict[str, WirelessNode], Dict[str, int]]:
    node_ids = sort_nodes(physical_graph.nodes())
    nodes = {nid: WirelessNode(node_id=nid) for nid in node_ids}
    stats = {
        "hello_sent": 0,
        "lsa_originated": 0,
        "lsa_forwarded": 0,
        "lsa_accepted": 0,
        "lsa_dropped": 0,
        "rounds": 0,
    }

    print("\n" + "=" * 72)
    print(f"PHASE 1: NEIGHBOR DISCOVERY (HELLO BROADCAST) | Highlight: Node {origin_id}")
    print("=" * 72)

    for sender_id in node_ids:
        packet = HelloPacket(sender_id=sender_id)
        physical_neighbors = sort_nodes(physical_graph.neighbors(sender_id))
        stats["hello_sent"] += 1
        tag = _format_tag(origin_id, sender_id)
        print(
            f"{tag} HELLO TX | Node {sender_id} broadcasts HELLO -> {physical_neighbors}"
        )
        for nbr_id in physical_neighbors:
            nodes[nbr_id].receive_hello(packet)
            rx_tag = _format_tag(origin_id, sender_id, nbr_id)
            if nbr_id == origin_id or sender_id == origin_id:
                print(
                    f"{rx_tag} HELLO RX | Node {nbr_id} discovered 1-hop neighbor Node {sender_id}"
                )

    print(
        f"\n[Phase 1 Summary] Node {origin_id} neighbors: "
        f"{sort_nodes(nodes[origin_id].neighbors)}"
    )

    print("\n" + "=" * 72)
    print(f"PHASE 2: TOPOLOGY FLOODING (LSA) | Highlight: Node {origin_id}")
    print("=" * 72)

    # Queue items: (sender_id, receiver_id, lsa_packet)
    in_flight: deque[Tuple[str, str, LSAPacket]] = deque()

    for nid in node_ids:
        lsa = nodes[nid].create_lsa(seq_num=1)
        stats["lsa_originated"] += 1
        targets = sort_nodes(nodes[nid].neighbors)
        tag = _format_tag(origin_id, nid)
        print(
            f"{tag} LSA ORIGINATE | Node {nid} -> LSA(origin={lsa.origin_id}, "
            f"seq={lsa.seq_num}, neighbors={list(lsa.neighbors)}) to {targets}"
        )
        for target_id in targets:
            in_flight.append((nid, target_id, lsa))

    round_num = 0
    while in_flight:
        round_num += 1
        stats["rounds"] = round_num
        round_size = len(in_flight)
        next_round: deque[Tuple[str, str, LSAPacket]] = deque()
        print(f"\n--- Flooding Round {round_num} ({round_size} packets in transit) ---")

        for _ in range(round_size):
            sender_id, receiver_id, lsa = in_flight.popleft()
            accepted, forward_targets = nodes[receiver_id].receive_lsa(lsa, sender_id)
            tag = _format_tag(origin_id, sender_id, receiver_id, lsa.origin_id)

            if accepted:
                stats["lsa_accepted"] += 1
                fwd_info = (
                    f" -> forward to {forward_targets}"
                    if forward_targets
                    else " -> no further hops"
                )
                if tag.strip():
                    print(
                        f"{tag} LSA RX/ACCEPT | Node {receiver_id} <- from {sender_id} "
                        f"[LSA origin={lsa.origin_id}, seq={lsa.seq_num}]{fwd_info}"
                    )
                for target_id in forward_targets:
                    stats["lsa_forwarded"] += 1
                    next_round.append((receiver_id, target_id, lsa))
            else:
                stats["lsa_dropped"] += 1
                if tag.strip():
                    print(
                        f"{tag} LSA RX/DROP   | Node {receiver_id} <- from {sender_id} "
                        f"[duplicate LSA origin={lsa.origin_id}, seq={lsa.seq_num}]"
                    )

        converged_count = sum(
            1
            for node in nodes.values()
            if node.local_graph.number_of_nodes() == physical_graph.number_of_nodes()
            and node.local_graph.number_of_edges() == physical_graph.number_of_edges()
        )
        print(
            f"[Round {round_num} Status] Converged nodes: "
            f"{converged_count}/{len(nodes)}"
        )
        in_flight = next_round

    for node in nodes.values():
        node.compute_routing_table()

    print("\n" + "=" * 72)
    print("DISCOVERY & CONVERGENCE SUMMARY")
    print("=" * 72)
    print(f"Nodes converged: {len(nodes)}/{len(nodes)}")
    print(
        f"HELLO broadcasts: {stats['hello_sent']} | "
        f"LSAs originated: {stats['lsa_originated']} | "
        f"LSAs forwarded: {stats['lsa_forwarded']}"
    )
    print(
        f"LSA deliveries accepted: {stats['lsa_accepted']} | "
        f"Duplicates dropped: {stats['lsa_dropped']} | "
        f"Flooding rounds: {stats['rounds']}"
    )

    return nodes, stats


def print_routing_tables(nodes: Dict[str, WirelessNode]) -> None:
    print("\n" + "=" * 72)
    print("COMPUTED ROUTING TABLES (LOCAL SHORTEST-PATH PER NODE)")
    print("=" * 72)

    for nid in sort_nodes(nodes.keys()):
        node = nodes[nid]
        print(f"\nNode {nid} Routing Table:")
        header = f"  {'Destination':<12} {'Next Hop':<10} {'Cost (Hops)':<13} {'Full Path'}"
        print(header)
        print("  " + "-" * (len(header) + 10))
        for dest in sort_nodes(node.routing_table.keys()):
            entry = node.routing_table[dest]
            path_str = " -> ".join(entry.path)
            print(
                f"  {entry.destination:<12} {entry.next_hop:<10} "
                f"{entry.cost:<13} {path_str}"
            )


def prompt_num_nodes() -> int:
    while True:
        raw = input("Enter the number of wireless nodes (N >= 2): ").strip()
        try:
            value = int(raw)
            if value >= 2:
                return value
            print("Error: Number of nodes must be at least 2.")
        except ValueError:
            print(f"Error: '{raw}' is not a valid integer.")


def prompt_origin_node(available_nodes: List[str]) -> str:
    default_node = available_nodes[0]
    while True:
        raw = input(
            f"Enter origin node to trace discovery log [default: {default_node}]: "
        ).strip()
        if not raw:
            return default_node
        if raw in available_nodes:
            return raw
        print(f"Error: Node '{raw}' does not exist. Choose from: {', '.join(available_nodes)}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Distributed Link-State wireless network topology discovery simulator."
    )
    parser.add_argument(
        "num_nodes",
        type=int,
        nargs="?",
        help="Number of wireless nodes to generate (N >= 2)",
    )
    parser.add_argument(
        "--origin",
        type=str,
        default=None,
        help="Origin node ID to highlight in the discovery log",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible topologies",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.num_nodes is not None:
        if args.num_nodes < 2:
            print("[Error] Number of nodes must be at least 2.", file=sys.stderr)
            sys.exit(1)
        num_nodes = args.num_nodes
    else:
        num_nodes = prompt_num_nodes()

    physical_graph, layout = generate_connected_topology(num_nodes, seed=args.seed)
    available_nodes = sort_nodes(physical_graph.nodes())

    if args.origin is not None:
        if args.origin not in available_nodes:
            print(
                f"[Error] Origin node '{args.origin}' is not in 1..{num_nodes}.",
                file=sys.stderr,
            )
            sys.exit(1)
        origin_id = args.origin
    else:
        origin_id = prompt_origin_node(available_nodes)

    nodes, _ = simulate_link_state_discovery(physical_graph, origin_id=origin_id)
    print_routing_tables(nodes)

    discovered_graph = nodes[origin_id].local_graph

    plt.ion()
    render_graph(
        discovered_graph,
        layout,
        title=f"Discovered Wireless Topology (N={num_nodes}, E={discovered_graph.number_of_edges()})",
    )

    def lookup_route(src: str, dst: str) -> Tuple[List[str], float]:
        entry = nodes[src].routing_table[dst]
        return list(entry.path), float(entry.cost)

    try:
        run_interactive_cli(discovered_graph, layout, path_lookup=lookup_route)
    finally:
        plt.close("all")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nOperation cancelled by user (Ctrl+C). Exiting.")
        sys.exit(0)

