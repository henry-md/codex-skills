---
name: explain-tech
description: Explain an unfamiliar technology from the problem it solves through the common alternatives, value, mechanics, and tradeoffs. Use when someone asks what a technology, acronym, reserved keyword, platform service, protocol, or architecture term means and lacks the surrounding mental model.
---

# Explain Tech

Explain the technology so the reader understands why it exists, not only what its parts do.

## Writing base

Read and apply [`write-simply`](/Users/Henry/Developer/tenex-standards/skills/reference/write-simply/SKILL.md) before answering. This skill adds a problem-first structure for technical explanations. If that file is unavailable, continue with short, direct sentences and plain words.

Match the reader's stated knowledge. Start from a tool or behavior they already know. Do not assume that nearby cloud, networking, identity, database, or programming terms are understood.

## Explanation order

Give the explanation in this order. Use only as much formatting as the answer needs.

1. **Short answer:** In the first sentence, say what the thing is in plain English. In the second sentence, say what problem it solves.
2. **The problem before it existed:** Describe the normal setup without this technology. Show the concrete pain, failure, cost, or repeated work that caused people to create it.
3. **Common ways to solve that problem:** Enumerate the main real choices, including the technology being explained. Compare options that solve the same problem. Do not pad the list with adjacent products.
4. **Value:** State why a person or organization would choose this option. Tie each claimed feature to a concrete benefit.
5. **Mechanics:** Explain what changes under the hood. Trace one request, connection, build, query, or state change from start to finish when that helps.
6. **Tradeoffs:** Say what becomes harder, what it costs, and when a simpler alternative is better.

Do not lead with a feature list, vendor category, or component inventory. A reader should understand the need before the machinery.

## Names, acronyms, and keywords

On first use, expand every acronym that is not obvious to the reader. Write the full name first, then the acronym: `Virtual Private Cloud (VPC)`.

Immediately explain why the term has that name:

- For an acronym, explain how the expanded words describe the thing.
- For a descriptive product or protocol name, connect the name to its job.
- For a brand name, give the vendor's stated origin or rename history when known.
- If the origin is not public, say it is a brand name and that no official expansion is published. Do not invent an etymology.
- For a reserved keyword, explain what the language reserves it for and why that word describes the behavior.

Verify an expansion or name origin with a primary source when uncertain. State uncertainty plainly when the source does not answer it.

Do not introduce a second unexplained term while defining the first. If one is necessary, define it at once.

## Compare against the real baseline

Use the simplest common alternative as the baseline. For example:

- Compare a managed identity system with separate usernames and lasting passwords.
- Compare a private network path with a public address plus firewall rules.
- Compare an object store with files in a database or on one server's disk.
- Compare an Object-Relational Mapper (ORM) with handwritten Structured Query Language (SQL), then explain both names immediately.

When the reader names a familiar tool, trace from that tool. If they know Prisma, explain what Prisma hides before discussing the network, driver, protocol, or database service beneath it.

Distinguish layers that people often mix together. State which problem each layer solves. For a database connection, separate network reachability, transport encryption, authentication, authorization, query protocol, and application library when they matter.

## Value test

Do not say that a technology "provides identity," "adds security," or "stores secrets" and stop there. Explain the saved work or blocked failure.

Prefer claims such as:

- Disabling one employee account removes access from every connected app.
- A short-lived token removes a database password that teams would otherwise store and rotate.
- A private address prevents an internet host from opening a database connection before login is considered.

Before answering, check that the reader can now answer:

- What is it?
- What problem exists without it?
- What are the common alternatives?
- Why choose this one?
- What changes under the hood?
- What does its name mean?
- When is it the wrong choice?
