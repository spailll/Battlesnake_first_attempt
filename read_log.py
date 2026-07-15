import json
import os
import sys

LOG_FILE = os.environ.get(
    "LOG_FILE", "/home/ubuntu/Battlesnake_first_attempt/latest_game_log.jsonl"
)


def main():
    turn_filter = None
    if len(sys.argv) > 1:
        turn_filter = int(sys.argv[1])

    with open(LOG_FILE) as f:
        for line in f:
            record = json.loads(line)

            if record.get("event") == "game_start":
                print(f"=== Game {record['game_id']} ({record['ruleset']}) ===\n")
                continue

            turn = record["turn"]
            if turn_filter is not None and turn != turn_filter:
                continue

            print(f"--- Turn {turn}: chose '{record['chosen_move']}' "
                  f"({record['strategy']}, {record['game_mode']}) ---")
            if record.get("mode_mismatch"):
                print(f"  !!! MODE MISMATCH: running as '{record['game_mode']}' but the "
                      f"real ruleset is '{record.get('real_ruleset')}' -- check strategy.txt !!!")
            print(f"  My head: {record['my_head']}  health: {record['my_health']}  "
                  f"length: {record['my_length']}")
            print(f"  Food: {record['food']}")
            print(f"  Safe moves considered: {record['safe_moves']}")

            diag = record.get("diagnostics", {})
            if diag:
                print(f"  Search depth reached: {diag.get('depth_reached')}  "
                      f"(search: {diag.get('search_elapsed_ms', '?')}ms, "
                      f"total: {diag.get('total_elapsed_ms', '?')}ms)")
                root_scores = diag.get("root_scores", {})
                if root_scores:
                    print("  Full-search scores per direction:")
                    for d, s in root_scores.items():
                        print(f"    {d}: raw={s['raw_score']}  eat_bonus={s['eat_bonus']}")
                breakdown = diag.get("one_ply_breakdown", {})
                if breakdown:
                    print("  One-ply component breakdown:")
                    for d, comps in breakdown.items():
                        if comps.get("dead"):
                            print(f"    {d}: DIES")
                            continue
                        print(f"    {d}: total={comps.get('total')}  "
                              f"voronoi_term={comps.get('voronoi_term')}  "
                              f"length_term={comps.get('length_term')}  "
                              f"food_score={comps.get('food_score')} "
                              f"(dist={comps.get('nearest_food_dist')}, "
                              f"weight={comps.get('food_weight')})  "
                              f"health_score={comps.get('health_score')}  "
                              f"hazard_score={comps.get('hazard_score')}")
            print()


if __name__ == "__main__":
    main()