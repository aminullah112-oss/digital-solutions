/*
  Warnings:

  - You are about to drop the `AIEvent` table. If the table is not empty, all the data it contains will be lost.

*/
-- CreateEnum
CREATE TYPE "AiEventType" AS ENUM ('PROCESSING', 'AI_RESPONDED', 'HUMAN_HANDOFF', 'BOOKING_CREATED', 'LEAD_SCORED', 'FOLLOW_UP_CREATED', 'CUSTOMER_IDENTIFIED');

-- DropForeignKey
ALTER TABLE "AIEvent" DROP CONSTRAINT "AIEvent_conversationId_fkey";

-- DropTable
DROP TABLE "AIEvent";

-- DropEnum
DROP TYPE "AIEventType";

-- CreateTable
CREATE TABLE "AiEvent" (
    "id" TEXT NOT NULL,
    "type" "AiEventType" NOT NULL,
    "channel" "Channel" NOT NULL,
    "customerName" TEXT NOT NULL,
    "conversationId" TEXT,
    "summary" TEXT NOT NULL,
    "detail" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AiEvent_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "AiEvent_createdAt_idx" ON "AiEvent"("createdAt");

-- AddForeignKey
ALTER TABLE "AiEvent" ADD CONSTRAINT "AiEvent_conversationId_fkey" FOREIGN KEY ("conversationId") REFERENCES "Conversation"("id") ON DELETE SET NULL ON UPDATE CASCADE;
