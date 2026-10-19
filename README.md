# Wireless Networks - RSF0075 (3rd Phase 2026 - CPGEI)

Interactive graph shortest-path calculator and topology visualizer developed for the course **Redes sem fio - RSF0075 (3a fase 2026 - CPGEI)**.

## Overview

The application parses an undirected network topology from a plain-text file, renders the initial graph structure in a persistent visualization window, and provides a continuous terminal CLI loop to calculate shortest paths (via Dijkstra's algorithm) between any chosen nodes.

## File Format

Input files must follow the format below, ending with a blank line:

```text
ORIGIN DESTINATION WEIGHT