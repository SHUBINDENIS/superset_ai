"use client";

import { MessageSquare } from "lucide-react";

export function ChatEmpty() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="flex flex-col items-center gap-2">
        <MessageSquare className="h-10 w-10 text-muted-foreground" />
        <h2 className="text-lg font-medium">Диалог пока пуст</h2>
        <p className="max-w-sm text-sm text-muted-foreground">
          Задайте бизнес-вопрос ниже. Если сначала нужно понять, как
          лучше начать, откройте кнопку «Как начать» справа сверху.
        </p>
      </div>

      <div className="w-full max-w-2xl rounded-lg border bg-card p-4 text-left">
        <p className="text-sm font-medium">Как начать работу</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Чат подходит для прямых бизнес-вопросов. Для просмотра структуры
          данных сначала перейдите в предпросмотр, а если нужно найти
          подходящий источник, используйте сканер схем из подсказок.
        </p>
      </div>

      <div className="max-w-xl space-y-2 text-left text-xs text-muted-foreground">
        <p className="font-medium text-foreground">Как это работает</p>
        <ul className="list-disc space-y-1 pl-4">
          <li>
            Если вопрос понятен в бизнес-терминах (выручка, заказы, клиенты)
            — задайте его прямо в чате.
          </li>
          <li>
            Если нужно сначала увидеть данные и поля — откройте подсказки
            и перейдите в «Предпросмотр».
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
