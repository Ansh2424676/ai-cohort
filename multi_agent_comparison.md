# Day 22: Multi-Agent Orchestration Comparison

## Overview

Day 22 extends the Day 21 single-agent healthcare chatbot
into a multi-agent architecture using LangGraph.

The Day 22 workflow separates responsibilities into:

1. Router Agent
2. Coverage Specialist
3. Claims Specialist
4. Enrollment Specialist

The Router identifies the domain of the question and sends
the request to the appropriate specialist.

---

## Architecture

```text
                         User Question
                              |
                              v
                       +--------------+
                       | Router Agent |
                       +--------------+
                         /     |      \
                        /      |       \
                       v       v        v
                Coverage    Claims   Enrollment
                Specialist  Specialist Specialist
                    |          |          |
                    v          v          v
                 Answer      Answer     Answer