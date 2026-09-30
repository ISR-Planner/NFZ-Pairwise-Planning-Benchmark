"""
Target Allocator for Multi-Drone Mission Planning

Distributes targets among available drones based on various strategies
before individual drone route optimization.

This is a LangGraph-compatible tool.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set


class AllocationStrategy(str, Enum):
    """Available allocation strategies."""

    GEOGRAPHIC = (
        "geographic"  # Assign targets to geographically closest drone's airport
    )
    INSERTION = "insertion"  # Cheapest insertion - minimize total tour cost
    GREEDY = "greedy"  # Assign highest priority targets to nearest capable drone
    BALANCED = "balanced"  # Distribute targets evenly by count
    EFFICIENT = "efficient"  # Maximize priority/fuel ratio (auction-based)
    EXCLUSIVE = "exclusive"  # Prioritize targets only one drone can reach


class TargetAllocator:
    """
    Allocates targets to drones based on configurable strategies.

    Takes into account:
    - Drone capabilities (which target types each drone can handle)
    - Drone fuel budgets
    - Target priorities
    - Geographic distribution
    - Distance matrix (SAM-aware if available)
    """

    def __init__(self):
        self._distance_matrix: Optional[Dict[str, Any]] = None

    def set_distance_matrix(self, matrix_data: Dict[str, Any]):
        """Set the pre-calculated distance matrix for allocation decisions."""
        self._distance_matrix = matrix_data

    def allocate(
        self,
        targets: List[Dict[str, Any]],
        drone_configs: Dict[str, Dict[str, Any]],
        airports: List[Dict[str, Any]],
        strategy: AllocationStrategy = AllocationStrategy.EFFICIENT,
    ) -> Dict[str, List[str]]:
        """
        Allocate targets to drones using the specified strategy.

        Args:
            targets: List of target dicts with id, x, y, priority, type
            drone_configs: Dict of drone configs {
                "1": {"fuel_budget": 300, "target_access": {"A": true, ...},
                      "start_airport": "A1", "enabled": true},
                ...
            }
            airports: List of airport dicts
            strategy: Allocation strategy to use

        Returns:
            Dict mapping drone IDs to lists of assigned target IDs:
            {"1": ["T1", "T3"], "2": ["T2", "T4"], ...}
        """
        # Filter to enabled drones only
        active_drones = {
            did: cfg
            for did, cfg in drone_configs.items()
            if cfg.get("enabled", True) is not False
        }

        if not active_drones or not targets:
            return {did: [] for did in drone_configs.keys()}

        # Determine which targets each drone can access
        drone_capabilities = self._calculate_capabilities(targets, active_drones)

        # Call appropriate strategy
        if strategy == AllocationStrategy.GEOGRAPHIC:
            result = self._allocate_geographic(
                targets, active_drones, airports, drone_capabilities
            )
        elif strategy == AllocationStrategy.GREEDY:
            result = self._allocate_greedy(
                targets, active_drones, airports, drone_capabilities
            )
        elif strategy == AllocationStrategy.BALANCED:
            result = self._allocate_balanced(
                targets, active_drones, airports, drone_capabilities
            )
        elif strategy == AllocationStrategy.EFFICIENT:
            result = self._allocate_efficient(
                targets, active_drones, airports, drone_capabilities
            )
        elif strategy == AllocationStrategy.EXCLUSIVE:
            result = self._allocate_exclusive_first(
                targets, active_drones, airports, drone_capabilities
            )
        elif strategy == AllocationStrategy.INSERTION:
            result = self._allocate_insertion(
                targets, active_drones, airports, drone_capabilities
            )
        else:
            # Default to geographic (most intuitive)
            result = self._allocate_geographic(
                targets, active_drones, airports, drone_capabilities
            )

        # Log any unassigned targets for debugging
        all_target_ids = {str(t["id"]) for t in targets}
        assigned_ids = set()
        for tid_list in result.values():
            assigned_ids.update(tid_list)
        unassigned = all_target_ids - assigned_ids

        if unassigned:
            print(
                f"⚠️ ALLOCATOR: {len(unassigned)} targets NOT assigned: {sorted(unassigned)}",
                flush=True,
            )
            # Debug: check why each was skipped
            for tid in sorted(unassigned):
                capable_drones = [
                    did for did, caps in drone_capabilities.items() if tid in caps
                ]
                if not capable_drones:
                    print(
                        f"   {tid}: No drone has capability (type restriction)",
                        flush=True,
                    )
                else:
                    print(
                        f"   {tid}: Capable drones={capable_drones} but not assigned",
                        flush=True,
                    )

        return result

    def _calculate_capabilities(
        self, targets: List[Dict[str, Any]], drone_configs: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Set[str]]:
        """
        Calculate which targets each drone can access based on type restrictions.

        Returns:
            Dict mapping drone IDs to sets of accessible target IDs
        """
        capabilities: Dict[str, Set[str]] = {}

        for did, cfg in drone_configs.items():
            target_access = cfg.get("target_access", {})

            # If no types specified, allow all
            if not target_access:
                allowed_types = {"a", "b", "c", "d"}
            else:
                allowed_types = {
                    t.lower()
                    for t, enabled in target_access.items()
                    if enabled and isinstance(t, str)
                }

            # Find all targets this drone can reach
            accessible = set()
            for target in targets:
                target_type = str(target.get("type", "a")).lower()
                if target_type in allowed_types:
                    accessible.add(str(target["id"]))

            capabilities[did] = accessible

        return capabilities

    def _get_distance(
        self, from_id: str, to_id: str, waypoints: Optional[List[Dict[str, Any]]] = None
    ) -> float:
        """Get distance between two waypoints from matrix or calculate directly."""
        if self._distance_matrix:
            labels = self._distance_matrix.get("labels", [])
            matrix = self._distance_matrix.get("matrix", [])

            try:
                i = labels.index(from_id)
                j = labels.index(to_id)
                return matrix[i][j]
            except (ValueError, IndexError):
                pass

        # Per policy: SAM-aware only. If matrix lookup failed, fail loudly
        # rather than silently fall back to Euclidean.
        raise RuntimeError(
            f"target_allocator: cannot find SAM-aware distance for "
            f"{from_id}→{to_id}. Matrix lookup failed; Euclidean fallback "
            f"is disabled (policy)."
        )

    def _allocate_geographic(
        self,
        targets: List[Dict[str, Any]],
        drone_configs: Dict[str, Dict[str, Any]],
        airports: List[Dict[str, Any]],
        capabilities: Dict[str, Set[str]],
    ) -> Dict[str, List[str]]:
        """
        Geographic allocation: assign each target to the drone whose starting
        airport is closest to that target (using SAM-aware distances if available).

        This naturally creates geographic clusters - targets near A1 go to
        drones starting at A1, targets near A2 go to drones starting at A2.

        Simple and intuitive, produces balanced geographic distribution.
        """
        assignments: Dict[str, List[str]] = {did: [] for did in drone_configs.keys()}

        airport_by_id = {str(a["id"]): a for a in airports}
        waypoints = airports + targets

        # Get each drone's starting airport ID
        drone_start_airports: Dict[str, str] = {}
        for did, cfg in drone_configs.items():
            start_id = cfg.get("start_airport", cfg.get("startAirport", f"A{did}"))
            if start_id not in airport_by_id and airports:
                start_id = airports[0]["id"]
            drone_start_airports[did] = start_id

        # For each target, assign to the drone whose START AIRPORT is closest
        for target in targets:
            tid = str(target["id"])

            candidates = []

            for did in drone_configs.keys():
                # Check capability
                if tid not in capabilities[did]:
                    continue

                start_airport_id = drone_start_airports.get(did)
                if not start_airport_id:
                    continue

                # Use SAM-aware distance from matrix if available, else Euclidean
                distance = self._get_distance(start_airport_id, tid, waypoints)
                candidates.append((did, distance))

            if not candidates:
                continue

            best_distance = min(distance for _did, distance in candidates)
            tied = [
                did
                for did, distance in candidates
                if abs(distance - best_distance) <= 1e-9
            ]
            best_drone = min(tied, key=lambda did: (len(assignments[did]), did))
            assignments[best_drone].append(tid)

        return assignments

    def _allocate_greedy(
        self,
        targets: List[Dict[str, Any]],
        drone_configs: Dict[str, Dict[str, Any]],
        airports: List[Dict[str, Any]],
        capabilities: Dict[str, Set[str]],
    ) -> Dict[str, List[str]]:
        """
        Greedy allocation: assign highest priority targets to nearest capable drone.

        Fast but may not be optimal for overall efficiency.
        """
        # Sort targets by priority (highest first)
        sorted_targets = sorted(
            targets, key=lambda t: int(t.get("priority", 5)), reverse=True
        )

        assignments: Dict[str, List[str]] = {did: [] for did in drone_configs.keys()}
        assigned_ids: Set[str] = set()

        # Build waypoints list for distance calculation
        waypoints = airports + targets

        # Get drone starting positions
        drone_positions: Dict[str, str] = {}
        airport_by_id = {str(a["id"]): a for a in airports}

        for did, cfg in drone_configs.items():
            start_id = cfg.get("start_airport", f"A{did}")
            if start_id not in airport_by_id:
                start_id = airports[0]["id"] if airports else None
            drone_positions[did] = start_id

        for target in sorted_targets:
            tid = str(target["id"])

            if tid in assigned_ids:
                continue

            # Find nearest capable drone
            best_drone = None
            best_distance = float("inf")

            for did in drone_configs.keys():
                if tid not in capabilities[did]:
                    continue

                # Calculate distance from drone's current position to target
                drone_pos = drone_positions.get(did)
                if not drone_pos:
                    continue

                distance = self._get_distance(drone_pos, tid, waypoints)

                if distance < best_distance:
                    best_distance = distance
                    best_drone = did

            if best_drone:
                assignments[best_drone].append(tid)
                assigned_ids.add(tid)
                # Update drone position to last assigned target
                drone_positions[best_drone] = tid

        return assignments

    def _allocate_balanced(
        self,
        targets: List[Dict[str, Any]],
        drone_configs: Dict[str, Dict[str, Any]],
        airports: List[Dict[str, Any]],
        capabilities: Dict[str, Set[str]],
    ) -> Dict[str, List[str]]:
        """
        Balanced allocation: distribute targets evenly by count.

        Ensures each drone gets approximately the same number of targets.
        """
        assignments: Dict[str, List[str]] = {did: [] for did in drone_configs.keys()}
        assigned_ids: Set[str] = set()

        # Sort targets by priority
        sorted_targets = sorted(
            targets, key=lambda t: int(t.get("priority", 5)), reverse=True
        )

        # Calculate target quota per drone
        num_drones = len(drone_configs)
        targets_per_drone = len(targets) // num_drones
        extra = len(targets) % num_drones
        # 1-based ordinal per drone id — virtual ids ("1_L1") aren't int-parseable,
        # so use insertion order instead of int(did) for the "extra" bonus check.
        drone_ordinal = {did: i + 1 for i, did in enumerate(drone_configs.keys())}

        # Build waypoints list for distance calculation
        waypoints = airports + targets

        # Get drone starting positions
        drone_positions: Dict[str, str] = {}
        airport_by_id = {str(a["id"]): a for a in airports}

        for did, cfg in drone_configs.items():
            start_id = cfg.get("start_airport", f"A{did}")
            if start_id not in airport_by_id:
                start_id = airports[0]["id"] if airports else None
            drone_positions[did] = start_id

        for target in sorted_targets:
            tid = str(target["id"])

            if tid in assigned_ids:
                continue

            # Find drone with fewest assignments that can handle this target
            best_drone = None
            min_assignments = float("inf")
            best_distance = float("inf")

            for did in drone_configs.keys():
                if tid not in capabilities[did]:
                    continue

                current_count = len(assignments[did])

                # Check if drone can take more targets
                max_for_drone = targets_per_drone + (
                    1 if drone_ordinal[did] <= extra else 0
                )
                if current_count >= max_for_drone:
                    continue

                # Prefer drone with fewer assignments; break ties by distance
                drone_pos = drone_positions.get(did)
                distance = (
                    self._get_distance(drone_pos, tid, waypoints)
                    if drone_pos
                    else float("inf")
                )

                if current_count < min_assignments or (
                    current_count == min_assignments and distance < best_distance
                ):
                    min_assignments = current_count
                    best_distance = distance
                    best_drone = did

            if best_drone:
                assignments[best_drone].append(tid)
                assigned_ids.add(tid)
                drone_positions[best_drone] = tid

        return assignments

    def _allocate_efficient(
        self,
        targets: List[Dict[str, Any]],
        drone_configs: Dict[str, Dict[str, Any]],
        airports: List[Dict[str, Any]],
        capabilities: Dict[str, Set[str]],
    ) -> Dict[str, List[str]]:
        """
        Efficient allocation: maximize priority/distance ratio (auction-style).

        Each target goes to the drone that gets the best "value" for reaching it.
        """
        assignments: Dict[str, List[str]] = {did: [] for did in drone_configs.keys()}
        assigned_ids: Set[str] = set()

        # Sort targets by priority
        sorted_targets = sorted(
            targets, key=lambda t: int(t.get("priority", 5)), reverse=True
        )

        # Build waypoints list for distance calculation
        waypoints = airports + targets

        # Get drone starting positions
        drone_positions: Dict[str, str] = {}
        airport_by_id = {str(a["id"]): a for a in airports}

        for did, cfg in drone_configs.items():
            start_id = cfg.get("start_airport", f"A{did}")
            if start_id not in airport_by_id:
                start_id = airports[0]["id"] if airports else None
            drone_positions[did] = start_id

        for target in sorted_targets:
            tid = str(target["id"])
            priority = int(target.get("priority", 5))

            if tid in assigned_ids:
                continue

            # Find drone with best efficiency for this target
            best_drone = None
            best_efficiency = float("-inf")  # Allow any efficiency, even 0 or negative

            for did in drone_configs.keys():
                if tid not in capabilities[did]:
                    continue

                # Calculate efficiency: priority / distance
                drone_pos = drone_positions.get(did)
                if not drone_pos:
                    continue

                distance = self._get_distance(drone_pos, tid, waypoints)

                # Avoid division by zero; treat infinity as very large distance
                if distance == float("inf"):
                    # Still allow assignment but with minimal efficiency
                    efficiency = 0.0
                elif distance <= 0:
                    distance = 0.1
                    efficiency = priority / distance
                else:
                    efficiency = priority / distance

                if efficiency > best_efficiency:
                    best_efficiency = efficiency
                    best_drone = did

            if best_drone:
                assignments[best_drone].append(tid)
                assigned_ids.add(tid)
                drone_positions[best_drone] = tid

        return assignments

    def _allocate_exclusive_first(
        self,
        targets: List[Dict[str, Any]],
        drone_configs: Dict[str, Dict[str, Any]],
        airports: List[Dict[str, Any]],
        capabilities: Dict[str, Set[str]],
    ) -> Dict[str, List[str]]:
        """
        Exclusive-first allocation: prioritize targets only one drone can reach.

        Ensures unique capabilities are utilized before general assignments.
        """
        assignments: Dict[str, List[str]] = {did: [] for did in drone_configs.keys()}
        assigned_ids: Set[str] = set()

        # Build waypoints list for distance calculation
        waypoints = airports + targets

        # Get drone starting positions
        drone_positions: Dict[str, str] = {}
        airport_by_id = {str(a["id"]): a for a in airports}

        for did, cfg in drone_configs.items():
            start_id = cfg.get("start_airport", f"A{did}")
            if start_id not in airport_by_id:
                start_id = airports[0]["id"] if airports else None
            drone_positions[did] = start_id

        # Sort targets by priority
        sorted_targets = sorted(
            targets, key=lambda t: int(t.get("priority", 5)), reverse=True
        )

        # First pass: assign targets only one drone can handle
        for target in sorted_targets:
            tid = str(target["id"])

            if tid in assigned_ids:
                continue

            # Find all drones that can handle this target
            capable_drones = [
                did for did in drone_configs.keys() if tid in capabilities[did]
            ]

            if len(capable_drones) == 1:
                # Only one drone can handle this target
                did = capable_drones[0]
                assignments[did].append(tid)
                assigned_ids.add(tid)
                drone_positions[did] = tid

        # Second pass: use insertion strategy for remaining targets (minimizes fuel)
        remaining_targets = [
            t for t in sorted_targets if str(t["id"]) not in assigned_ids
        ]

        if remaining_targets:
            # Use the insertion algorithm for remaining targets
            # Initialize tours with already-assigned targets
            drone_tours: Dict[str, List[str]] = {}
            for did, cfg in drone_configs.items():
                start_id = cfg.get("start_airport", cfg.get("startAirport", "A1"))
                end_id = cfg.get("end_airport", cfg.get("endAirport", start_id))
                if start_id not in airport_by_id:
                    start_id = airports[0]["id"] if airports else "A1"
                if end_id not in airport_by_id:
                    end_id = start_id
                # Build tour with already assigned targets in order
                tour = [start_id] + assignments[did] + [end_id]
                drone_tours[did] = tour

            unassigned = [str(t["id"]) for t in remaining_targets]

            while unassigned:
                best_target = None
                best_drone = None
                best_insertion_cost = float("inf")
                best_insertion_position = 0

                for tid in unassigned:
                    for did in drone_configs.keys():
                        if tid not in capabilities[did]:
                            continue

                        tour = drone_tours[did]
                        for pos in range(1, len(tour)):
                            prev_node = tour[pos - 1]
                            next_node = tour[pos]

                            old_cost = self._get_distance(
                                prev_node, next_node, waypoints
                            )
                            cost_to_target = self._get_distance(
                                prev_node, tid, waypoints
                            )
                            cost_from_target = self._get_distance(
                                tid, next_node, waypoints
                            )

                            if old_cost == float("inf"):
                                old_cost = 1000000
                            if cost_to_target == float("inf"):
                                cost_to_target = 1000000
                            if cost_from_target == float("inf"):
                                cost_from_target = 1000000

                            insertion_cost = (
                                cost_to_target + cost_from_target - old_cost
                            )

                            if insertion_cost < best_insertion_cost:
                                best_insertion_cost = insertion_cost
                                best_target = tid
                                best_drone = did
                                best_insertion_position = pos

                if best_target and best_drone:
                    assignments[best_drone].append(best_target)
                    assigned_ids.add(best_target)
                    unassigned.remove(best_target)
                    drone_tours[best_drone].insert(best_insertion_position, best_target)
                else:
                    break

        return assignments

    def _allocate_insertion(
        self,
        targets: List[Dict[str, Any]],
        drone_configs: Dict[str, Dict[str, Any]],
        airports: List[Dict[str, Any]],
        capabilities: Dict[str, Set[str]],
    ) -> Dict[str, List[str]]:
        """
        Cheapest Insertion allocation: minimize total tour cost.

        For each unassigned target, find which drone can add it to their tour
        with the minimum increase in total distance. This naturally creates
        efficient spatial clusters.

        Algorithm:
        1. Initialize each drone with empty tour (start_airport -> end_airport)
        2. For each target, compute insertion cost for each drone
        3. Assign target to drone with lowest insertion cost
        4. Update that drone's tour
        5. Repeat until all targets assigned
        """
        assignments: Dict[str, List[str]] = {did: [] for did in drone_configs.keys()}
        assigned_ids: Set[str] = set()

        # Build waypoints list for distance calculation
        waypoints = airports + targets
        airport_by_id = {str(a["id"]): a for a in airports}

        # Initialize tours for each drone: [start_airport, end_airport]
        drone_tours: Dict[str, List[str]] = {}
        for did, cfg in drone_configs.items():
            start_id = cfg.get("start_airport", cfg.get("startAirport", "A1"))
            end_id = cfg.get("end_airport", cfg.get("endAirport", start_id))
            # Ensure airports exist
            if start_id not in airport_by_id:
                start_id = airports[0]["id"] if airports else "A1"
            if end_id not in airport_by_id:
                end_id = start_id
            drone_tours[did] = [start_id, end_id]

        # Process all targets (no priority sorting - we want minimum fuel, not priority)
        unassigned_targets = [str(t["id"]) for t in targets]

        while unassigned_targets:
            best_target = None
            best_drone = None
            best_insertion_cost = float("inf")
            best_insertion_position = 0

            for tid in unassigned_targets:
                for did in drone_configs.keys():
                    # Check if drone can handle this target
                    if tid not in capabilities[did]:
                        continue

                    # Find cheapest position to insert this target in drone's tour
                    tour = drone_tours[did]
                    for pos in range(1, len(tour)):  # Insert between existing points
                        # Current edge: tour[pos-1] -> tour[pos]
                        # New edges: tour[pos-1] -> tid -> tour[pos]
                        prev_node = tour[pos - 1]
                        next_node = tour[pos]

                        # Cost of current edge
                        old_cost = self._get_distance(prev_node, next_node, waypoints)

                        # Cost of new edges
                        cost_to_target = self._get_distance(prev_node, tid, waypoints)
                        cost_from_target = self._get_distance(tid, next_node, waypoints)

                        # Handle infinity
                        if old_cost == float("inf"):
                            old_cost = 1000000
                        if cost_to_target == float("inf"):
                            cost_to_target = 1000000
                        if cost_from_target == float("inf"):
                            cost_from_target = 1000000

                        # Insertion cost = new edges - old edge
                        insertion_cost = cost_to_target + cost_from_target - old_cost

                        if insertion_cost < best_insertion_cost:
                            best_insertion_cost = insertion_cost
                            best_target = tid
                            best_drone = did
                            best_insertion_position = pos

            # Assign the best target to the best drone
            if best_target and best_drone:
                assignments[best_drone].append(best_target)
                assigned_ids.add(best_target)
                unassigned_targets.remove(best_target)

                # Update the drone's tour
                drone_tours[best_drone].insert(best_insertion_position, best_target)
            else:
                # No valid assignment found (shouldn't happen if capabilities are correct)
                break

        return assignments


# Global allocator instance
_allocator = TargetAllocator()


def allocate_targets(
    env: Dict[str, Any],
    drone_configs: Dict[str, Dict[str, Any]],
    strategy: str = "insertion",
    distance_matrix: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[str]]:
    """
    Allocate targets to drones using the specified strategy.

    This is the main entry point for use as a LangGraph tool.

    Args:
        env: Environment dict with targets, airports, sams
        drone_configs: Dict of drone configurations
        strategy: Allocation strategy ("insertion", "greedy", "balanced",
                  "efficient", "exclusive")
        distance_matrix: Pre-calculated SAM-aware distance matrix (optional)

    Returns:
        Dict mapping drone IDs to lists of target IDs
    """
    if distance_matrix:
        _allocator.set_distance_matrix(distance_matrix)

    targets = env.get("targets", [])
    airports = list(env.get("airports", []))  # Make a copy to avoid modifying original

    # Add checkpoints (C1, C2, etc.) for segmented mission replanning
    # Checkpoints act like airports - drones can start from these positions
    for checkpoint in env.get("checkpoints", []):
        airports.append(
            {
                "id": str(checkpoint["id"]),
                "x": float(checkpoint["x"]),
                "y": float(checkpoint["y"]),
                "is_checkpoint": True,
            }
        )

    # Add synthetic start nodes (for checkpoint replanning - legacy support)
    # These act like airports - drones can start from these positions
    for node_id, node_data in env.get("synthetic_starts", {}).items():
        airports.append(
            {
                "id": str(node_id),
                "x": float(node_data["x"]),
                "y": float(node_data["y"]),
                "is_synthetic": True,
            }
        )

    # Filter out excluded targets (e.g., targets inside SAM zones)
    if distance_matrix:
        excluded = set(distance_matrix.get("excluded_targets", []))
        if excluded:
            original_count = len(targets)
            targets = [t for t in targets if str(t["id"]) not in excluded]
            if len(targets) < original_count:
                print(
                    f"⚠️ Filtered out {original_count - len(targets)} excluded targets "
                    f"(inside SAM zones): {excluded}",
                    flush=True,
                )

    # Convert strategy string to enum
    try:
        strat_enum = AllocationStrategy(strategy.lower())
    except ValueError:
        strat_enum = AllocationStrategy.INSERTION

    return _allocator.allocate(targets, drone_configs, airports, strat_enum)


def set_allocator_matrix(matrix_data: Dict[str, Any]):
    """Set the distance matrix for the global allocator."""
    _allocator.set_distance_matrix(matrix_data)


def clear_allocator_matrix():
    """Clear the cached distance matrix from the global allocator.

    This should be called before each fresh solve to ensure the allocator
    doesn't use stale distance data from a previous environment state.
    """
    _allocator._distance_matrix = None


# ============================================================================
# Priority-Based Constraint Parsing
# ============================================================================

import re
from typing import Callable


def parse_priority_constraints(
    constraints_str: str,
) -> Dict[str, Callable[[int], bool]]:
    """
    Parse natural language priority constraints into filter functions.

    Supports formats like:
    - "D1,D2: priority>=6; D3,D4: priority<=6"
    - "D1: priority>5; D2,D3: priority<8"
    - "D1,D2: priority=10"

    Args:
        constraints_str: Constraint string with drone:condition pairs separated by semicolons

    Returns:
        Dict mapping drone IDs to filter functions: {"1": lambda p: p >= 6, ...}
    """
    filters: Dict[str, Callable[[int], bool]] = {}

    if not constraints_str or not constraints_str.strip():
        return filters

    # Split by semicolon to get individual constraints
    parts = constraints_str.split(";")

    for part in parts:
        part = part.strip()
        if not part or ":" not in part:
            continue

        # Split into drone list and condition
        try:
            drone_part, condition = part.split(":", 1)
        except ValueError:
            continue

        # Parse drone IDs (e.g., "D1,D2" or "D1, D2" or "1,2")
        drone_ids = []
        for d in drone_part.split(","):
            d = d.strip().upper().replace("D", "")
            if d.isdigit():
                drone_ids.append(d)

        # Parse condition (e.g., "priority>=6" or "priority > 6")
        condition = condition.strip().lower().replace(" ", "")

        # Match patterns like "priority>=6", "priority>5", "priority<=8", "priority<7", "priority=10"
        match = re.match(r"priority\s*(>=|<=|>|<|=)\s*(\d+)", condition)
        if not match:
            print(f"⚠️ Could not parse constraint: {condition}", flush=True)
            continue

        op = match.group(1)
        threshold = int(match.group(2))

        if op not in (">=", "<=", ">", "<", "="):
            continue

        # Create filter function based on operator
        def _make_filter(operator, thresh):
            def _fn(p):
                if operator == ">=":
                    return p >= thresh
                if operator == "<=":
                    return p <= thresh
                if operator == ">":
                    return p > thresh
                if operator == "<":
                    return p < thresh
                return p == thresh

            return _fn

        filter_func = _make_filter(op, threshold)

        # Assign filter to each drone
        for did in drone_ids:
            filters[did] = filter_func
            print(f"📋 D{did}: priority {op} {threshold}", flush=True)

    return filters


def allocate_with_priority_filters(
    env: Dict[str, Any],
    drone_configs: Dict[str, Dict[str, Any]],
    priority_filters: Dict[str, Callable[[int], bool]],
    strategy: str = "insertion",
    distance_matrix: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[str]]:
    """
    Allocate targets with per-drone priority filters applied.

    Args:
        env: Environment dict
        drone_configs: Drone configurations
        priority_filters: Dict mapping drone IDs to priority filter functions
        strategy: Allocation strategy
        distance_matrix: Pre-calculated distance matrix

    Returns:
        Dict mapping drone IDs to lists of target IDs
    """
    if distance_matrix:
        _allocator.set_distance_matrix(distance_matrix)

    targets = env.get("targets", [])
    airports = env.get("airports", [])

    # Filter out excluded targets (e.g., targets inside SAM zones)
    if distance_matrix:
        excluded = set(distance_matrix.get("excluded_targets", []))
        if excluded:
            targets = [t for t in targets if str(t["id"]) not in excluded]

    # Apply priority filters to determine which targets each drone can see
    # We'll create a modified drone_configs with adjusted target_access
    modified_configs = {}

    for did, cfg in drone_configs.items():
        if not cfg.get("enabled", True):
            continue

        # Start with existing config
        modified_cfg = dict(cfg)

        # If there's a priority filter for this drone, we need to track allowed targets
        if did in priority_filters:
            filter_func = priority_filters[did]

            # Get targets that pass the priority filter
            allowed_targets = set()
            for t in targets:
                priority = int(t.get("priority", 5))
                if filter_func(priority):
                    allowed_targets.add(str(t["id"]))

            # Store allowed targets in config for the allocator to use
            modified_cfg["_priority_allowed_targets"] = allowed_targets
            print(
                f"🎯 D{did}: {len(allowed_targets)} targets pass priority filter",
                flush=True,
            )

        modified_configs[did] = modified_cfg

    # Use a modified allocator that respects priority filters
    return _allocate_with_priority_internal(
        targets, modified_configs, airports, strategy, distance_matrix
    )


def _allocate_with_priority_internal(
    targets: List[Dict[str, Any]],
    drone_configs: Dict[str, Dict[str, Any]],
    airports: List[Dict[str, Any]],
    strategy: str,
    distance_matrix: Optional[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """
    Internal allocation that respects priority filters stored in configs.
    """
    if distance_matrix:
        _allocator.set_distance_matrix(distance_matrix)

    # Calculate capabilities with priority filter applied
    capabilities: Dict[str, Set[str]] = {}

    for did, cfg in drone_configs.items():
        target_access = cfg.get("target_access", {})
        priority_allowed = cfg.get("_priority_allowed_targets")  # May be None

        # If no types specified, allow all
        if not target_access:
            allowed_types = {"a", "b", "c", "d", "e"}
        else:
            allowed_types = {
                t.lower()
                for t, enabled in target_access.items()
                if enabled and isinstance(t, str)
            }

        # Find all targets this drone can reach
        accessible = set()
        for target in targets:
            tid = str(target["id"])
            target_type = str(target.get("type", "a")).lower()

            # Check type access
            if target_type not in allowed_types:
                continue

            # Check priority filter if present
            if priority_allowed is not None and tid not in priority_allowed:
                continue

            accessible.add(tid)

        capabilities[did] = accessible

    # Convert strategy string to enum
    try:
        strat_enum = AllocationStrategy(strategy.lower())
    except ValueError:
        strat_enum = AllocationStrategy.INSERTION

    # Call the appropriate strategy method
    if strat_enum == AllocationStrategy.GREEDY:
        return _allocator._allocate_greedy(
            targets, drone_configs, airports, capabilities
        )
    elif strat_enum == AllocationStrategy.BALANCED:
        return _allocator._allocate_balanced(
            targets, drone_configs, airports, capabilities
        )
    elif strat_enum == AllocationStrategy.EFFICIENT:
        return _allocator._allocate_efficient(
            targets, drone_configs, airports, capabilities
        )
    elif strat_enum == AllocationStrategy.EXCLUSIVE:
        return _allocator._allocate_exclusive_first(
            targets, drone_configs, airports, capabilities
        )
    elif strat_enum == AllocationStrategy.INSERTION:
        return _allocator._allocate_insertion(
            targets, drone_configs, airports, capabilities
        )
    else:
        return _allocator._allocate_insertion(
            targets, drone_configs, airports, capabilities
        )


# Tool definition for LangGraph
TARGET_ALLOCATOR_TOOL = {
    "name": "allocate_targets",
    "description": """Allocate targets to drones using various strategies before route optimization.
    Available strategies:
    - insertion: Cheapest insertion - minimize total tour cost (recommended)
    - greedy: Assign highest priority targets to nearest capable drone
    - balanced: Distribute targets evenly by count
    - efficient: Maximize priority/distance ratio
    - exclusive: Prioritize targets only one drone can reach first""",
    "parameters": {
        "type": "object",
        "properties": {
            "env": {
                "type": "object",
                "description": "Environment data containing targets, airports, and sams",
            },
            "drone_configs": {
                "type": "object",
                "description": "Drone configurations with capabilities and fuel budgets",
            },
            "strategy": {
                "type": "string",
                "description": "Allocation strategy to use",
                "enum": ["insertion", "greedy", "balanced", "efficient", "exclusive"],
                "default": "insertion",
            },
            "distance_matrix": {
                "type": "object",
                "description": "Pre-calculated SAM-aware distance matrix (optional)",
            },
        },
        "required": ["env", "drone_configs"],
    },
    "function": allocate_targets,
}
