class PipelineRunner:
    def __init__(self, steps):
        self.steps = steps

    def run(self, context):
        for step in self.steps:
            context = step.execute(context)

            if getattr(context, "enable_debug_trace", False):
                context.stage_trace.append(
                    {
                        "stage": step.__class__.__name__,
                        "has_spine": context.spine_weeks is not None,
                        "has_totals": context.weekly_totals is not None,
                        "has_distribution": context.workout_distribution is not None,
                        "has_details": context.detailed_plan is not None,
                        "has_validation": context.validation is not None,
                    }
                )

            if getattr(context, "_abort_return", None) is not None:
                break
        return context
