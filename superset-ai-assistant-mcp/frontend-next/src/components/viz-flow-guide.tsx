"use client";

import { CheckCircle2, Circle, CircleDot } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type VizFlowStep = "preview" | "recommend" | "share";

interface VizFlowGuideProps {
  currentStep: VizFlowStep;
  hasPreview: boolean;
  hasRecommendation: boolean;
}

const STEP_ORDER: VizFlowStep[] = ["preview", "recommend", "share"];

const STEP_LABELS: Record<
  VizFlowStep,
  { step: string; title: string; description: string }
> = {
  preview: {
    step: "1",
    title: "Посмотреть данные",
    description:
      "Проверьте строки и поля, чтобы убедиться, что источник выбран правильно.",
  },
  recommend: {
    step: "2",
    title: "Выбрать тип графика",
    description:
      "Используйте preview-контекст, чтобы быстро получить ориентир по визуализации.",
  },
  share: {
    step: "3",
    title: "Создать и открыть",
    description:
      "Создайте график и дашборд на основе уже выбранного источника и параметров.",
  },
};

function getStepState(
  step: VizFlowStep,
  currentStep: VizFlowStep,
  hasPreview: boolean,
  hasRecommendation: boolean,
) {
  if (step === "preview" && hasPreview) return "done";
  if (step === "recommend" && hasRecommendation) return "done";
  if (step === currentStep) return "current";
  return "upcoming";
}

export function VizFlowGuide(props: VizFlowGuideProps) {
  const { currentStep, hasPreview, hasRecommendation } = props;

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {STEP_ORDER.map((step) => {
        const state = getStepState(step, currentStep, hasPreview, hasRecommendation);
        const meta = STEP_LABELS[step];
        const Icon =
          state === "done"
            ? CheckCircle2
            : state === "current"
              ? CircleDot
              : Circle;

        return (
          <Card
            key={step}
            className={
              state === "current"
                ? "border-primary/40 bg-primary/5"
                : state === "done"
                  ? "border-emerald-200 bg-emerald-50/70"
                  : ""
            }
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Icon className="h-4 w-4" />
                {meta.step}. {meta.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {meta.description}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
