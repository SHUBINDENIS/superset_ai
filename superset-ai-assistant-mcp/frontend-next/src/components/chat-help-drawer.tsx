"use client";

import Link from "next/link";
import { BookOpenText, Eye, ScanSearch, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatHelpDrawerProps {
  open: boolean;
  onClose: () => void;
}

export function ChatHelpDrawer({ open, onClose }: ChatHelpDrawerProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <BookOpenText className="h-4 w-4 text-primary" />
            <p className="text-sm font-medium">Как работать с ассистентом</p>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Короткая памятка для текущего чата: когда задавать вопрос напрямую, а когда сначала посмотреть данные.
          </p>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="text-sm font-medium">Когда начинать с чата</p>
          <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
            <li>Сформулируйте вопрос в бизнес-терминах: метрика, сегмент, период.</li>
            <li>Если нужна быстрая гипотеза, начните прямо отсюда.</li>
            <li>Чат удобен для первого ответа и дальнейших уточнений.</li>
          </ul>
        </div>

        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="text-sm font-medium">Когда полезен предпросмотр</p>
          <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
            <li>Если нужно увидеть строки, поля и типы до вопроса.</li>
            <li>Если вы не уверены, где metric, dimension или дата.</li>
            <li>После preview легче перейти к рекомендациям и созданию графика.</li>
          </ul>
        </div>
      </div>

      <div className="mt-3 rounded-lg border bg-primary/5 p-3 text-xs text-muted-foreground">
        <p className="font-medium text-foreground">Рекомендуемая последовательность</p>
        <p className="mt-1">
          1. Задать бизнес-вопрос в чате или открыть preview.
          2. При необходимости посмотреть данные и поля.
          3. Подобрать тип графика.
          4. Создать chart/dashboard и открыть результат в Superset.
        </p>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">Подсказка по режимам</p>
          <p className="mt-1">
            `Бизнес` подойдёт для выводов и интерпретации. `Технический` лучше, когда нужны поля, допущения и структура ответа.
          </p>
        </div>
        <div className="rounded-lg border p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">Если источник неясен</p>
          <p className="mt-1">
            Если вы ещё не знаете, где искать данные, откройте сканер схем и посмотрите базы, таблицы и связи.
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <Button asChild size="sm">
          <Link href="/app/preview">
            <Eye className="mr-2 h-4 w-4" />
            Открыть предпросмотр
          </Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link href="/app/scan">
            <ScanSearch className="mr-2 h-4 w-4" />
            Открыть сканер схем
          </Link>
        </Button>
      </div>
    </div>
  );
}
