"use client";

import Link from "next/link";
import { MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";

const DIRECT_EXAMPLES = [
  "Покажи выручку по месяцам",
  "Какие категории товаров приносят больше всего продаж?",
  "Сравни регионы по количеству заказов",
  "Сделай график по заказам за 2025 год",
] as const;

const PREVIEW_EXAMPLES = [
  "Хочу быстро посмотреть несколько строк по заказам",
  "Помоги понять, где дата, сумма и категория",
  "Покажи данные так, чтобы я понял поля перед вопросом",
] as const;

interface ChatEmptyProps {
  onExampleClick: (text: string) => void;
}

export function ChatEmpty({ onExampleClick }: ChatEmptyProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="flex flex-col items-center gap-2">
        <MessageSquare className="h-10 w-10 text-muted-foreground" />
        <h2 className="text-lg font-medium">Диалог пока пуст</h2>
        <p className="max-w-sm text-sm text-muted-foreground">
          Задайте бизнес-вопрос ниже или выберите один из примеров.
          Ассистент поможет найти данные, построить график или собрать
          дашборд.
        </p>
      </div>

      <div className="grid w-full max-w-3xl gap-3 md:grid-cols-2">
        <div className="rounded-lg border bg-card p-4 text-left">
          <p className="text-sm font-medium">Хочу сразу задать бизнес-вопрос</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Используйте этот путь, если уже понимаете, о каких метриках,
            периодах или сегментах идёт речь.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {DIRECT_EXAMPLES.map((ex) => (
              <Button
                key={ex}
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => onExampleClick(ex)}
              >
                {ex}
              </Button>
            ))}
          </div>
        </div>

        <div className="rounded-lg border bg-card p-4 text-left">
          <p className="text-sm font-medium">Хочу быстро посмотреть данные</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Откройте предпросмотр, если сначала нужно увидеть строки, поля и
            понять структуру данных.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {PREVIEW_EXAMPLES.map((ex) => (
              <Button
                key={ex}
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => onExampleClick(ex)}
              >
                {ex}
              </Button>
            ))}
          </div>
          <Button asChild variant="secondary" size="sm" className="mt-3">
            <Link href="/app/preview">Открыть «Предпросмотр»</Link>
          </Button>
        </div>
      </div>

      <div className="max-w-xl space-y-2 text-left text-xs text-muted-foreground">
        <p className="font-medium text-foreground">Как это работает</p>
        <ul className="list-disc space-y-1 pl-4">
          <li>
            Если вопрос понятен в бизнес-терминах (выручка, заказы, клиенты)
            — задайте его прямо в чате.
          </li>
          <li>
            Если нужно сначала увидеть данные и поля — откройте
            «Предпросмотр» в боковой панели.
          </li>
          <li>
            Если вы ещё не знаете, где искать нужные данные, используйте
            «Сканер схем».
          </li>
        </ul>
      </div>
    </div>
  );
}
