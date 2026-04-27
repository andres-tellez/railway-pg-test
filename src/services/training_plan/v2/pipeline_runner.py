class PipelineRunner:
    def __init__(self, steps):
        self.steps = steps

    def run(self, context):
        for step in self.steps:
            context = step.execute(context)
            if getattr(context, "_abort_return", None) is not None:
                break
        return context
