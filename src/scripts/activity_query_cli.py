import argparse
from datetime import datetime, timedelta
from src.db.db_session import get_session
from src.db.dao.activity_stats_dao import ActivityStatsDAO
from src.utils.logger import get_logger
from src.utils.config import load_env

logger = get_logger(__name__)


def main(athlete_id: int, lookback_days: int, mode: str, metric: str = None):
    load_env()
    session = get_session()

    match mode:
        case "recent_activities":
            data = ActivityStatsDAO.get_recent_activities_by_athlete(
                session, athlete_id, lookback_days
            )
            print(f"\n✅ Retrieved {len(data)} recent activities:")
            for r in data:
                print(f"- {r['start_date']}: {r['name']}")

        case "fastest_run":
            r = ActivityStatsDAO.get_fastest_run(session, athlete_id, lookback_days)
            print(
                f"\n🚀 Fastest run: {r['name']} on {r['start_date']} @ pace {r['pace']:.2f} min/km"
            )

        case "longest_run":
            r = ActivityStatsDAO.get_longest_run(session, athlete_id, lookback_days)
            print(
                f"\n🏃‍♂️ Longest run: {r['name']} on {r['start_date']} — {r['distance_km']:.2f} km"
            )

        case "total_distance":
            end = datetime.utcnow()
            start = end - timedelta(days=lookback_days)
            stats = ActivityStatsDAO.get_total_distance(session, athlete_id, start, end)
            print(
                f"\n📊 Total distance: {stats['distance_km']:.2f} km, Time: {stats['duration_hours']:.2f} hrs"
            )

        case "weekly_summary":
            data = ActivityStatsDAO.get_weekly_summary(session, athlete_id)
            print("\n📅 Weekly summary:")
            for d in data:
                print(
                    f"- Week of {d['week_start']}: {d['total_distance_km']:.2f} km in {d['total_time_hr']:.2f} hrs"
                )

        case "hr_zone_summary":
            zones = ActivityStatsDAO.get_hr_zone_summary(
                session, athlete_id, lookback_days
            )
            print("\n❤️ HR Zone Summary:")
            for k, v in zones.items():
                print(f"- {k}: {v:.2f} min")

        case "treadmill_stats":
            stats = ActivityStatsDAO.get_treadmill_vs_outdoor_stats(
                session, athlete_id, lookback_days
            )
            print("\n🏠 vs 🌳:")
            for k, v in stats.items():
                print(f"- {k}: {v:.2f} %")

        case "weekday_pattern":
            days = ActivityStatsDAO.get_runs_by_weekday(
                session, athlete_id, lookback_days
            )
            print("\n🗓️ Runs by weekday:")
            for k, v in days.items():
                print(f"- {k}: {v}")

        case "time_of_day":
            times = ActivityStatsDAO.get_time_of_day_stats(
                session, athlete_id, lookback_days
            )
            print("\n🌞 vs 🌙:")
            for k, v in times.items():
                print(f"- {k}: {v}")

        case "trend_metric":
            if not metric:
                print("❌ Please provide --metric for trend_metric mode")
                return
            trend = ActivityStatsDAO.get_trend_metrics(session, athlete_id, metric)
            print(f"\n📈 {metric} trend:")
            for t in trend:
                print(f"- {t['period']}: {t['value']:.2f}")

        case _:
            print(f"❌ Unknown mode: {mode}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete_id", type=int, required=True)
    parser.add_argument("--lookback_days", type=int, default=30)
    parser.add_argument("--mode", type=str, required=True)
    parser.add_argument("--metric", type=str, help="Used for trend_metric mode")
    args = parser.parse_args()
    main(args.athlete_id, args.lookback_days, args.mode, args.metric)
