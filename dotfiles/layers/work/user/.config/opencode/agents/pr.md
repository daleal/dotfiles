---
description: Use this agent when you are asked to create PRs with the Fintoc PR style
hidden: true
request:
  body:
    temperature: 0.1
permissions:
  - action: edit
    resource: "*"
    effect: deny
  - action: linear_*
    resource: "*"
    effect: allow
---
