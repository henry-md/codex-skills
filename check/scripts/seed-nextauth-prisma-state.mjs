#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

function requireArg(value, message) {
  if (!value) {
    throw new Error(message);
  }

  return value;
}

function buildCookie(baseUrl, sessionToken, expiresAt) {
  const parsed = new URL(baseUrl);
  const secure = parsed.protocol === "https:";
  const cookieName = secure
    ? "__Secure-next-auth.session-token"
    : "next-auth.session-token";

  return {
    name: cookieName,
    value: sessionToken,
    domain: parsed.hostname,
    path: "/",
    expires: Math.floor(expiresAt.getTime() / 1000),
    httpOnly: true,
    secure,
    sameSite: "Lax",
  };
}

async function main() {
  const repoRoot = requireArg(
    process.argv[2],
    "Usage: seed-nextauth-prisma-state.mjs <repo-root> <output-path> <base-url> <email> <prisma-client-path> [adapter-package] [adapter-export]",
  );
  const outputPath = requireArg(process.argv[3], "Missing output path.");
  const baseUrl = requireArg(process.argv[4], "Missing base URL.");
  const email = requireArg(process.argv[5], "Missing email.");
  const prismaClientPath = requireArg(
    process.argv[6],
    "Missing Prisma client path.",
  );
  const adapterPackage = process.argv[7] || "";
  const adapterExport = process.argv[8] || "";
  const databaseUrl = requireArg(
    process.env.DATABASE_URL,
    "DATABASE_URL is required to seed a local NextAuth session.",
  );

  const absoluteRepoRoot = path.resolve(repoRoot);
  const absoluteOutputPath = path.resolve(absoluteRepoRoot, outputPath);
  const absoluteClientPath = path.resolve(absoluteRepoRoot, prismaClientPath);
  const clientModule = await import(pathToFileURL(absoluteClientPath).href);
  const PrismaClient = clientModule.PrismaClient;

  if (!PrismaClient) {
    throw new Error(
      `PrismaClient export was not found in ${absoluteClientPath}.`,
    );
  }

  let prisma;
  if (adapterPackage && adapterExport) {
    const requireFromRepo = createRequire(
      path.join(absoluteRepoRoot, "package.json"),
    );
    const adapterModule = requireFromRepo(adapterPackage);
    const AdapterClass = adapterModule[adapterExport];

    if (!AdapterClass) {
      throw new Error(
        `Adapter export ${adapterExport} was not found in ${adapterPackage}.`,
      );
    }

    prisma = new PrismaClient({
      adapter: new AdapterClass({ connectionString: databaseUrl }),
    });
  } else {
    prisma = new PrismaClient();
  }

  try {
    const user = await prisma.user.findUnique({
      where: { email },
      select: { id: true, email: true, name: true },
    });

    if (!user?.id) {
      throw new Error(
        `No local user exists for ${email}. Sign in normally once so the account is created, then retry /check.`,
      );
    }

    const now = new Date();
    const expires = new Date(now.getTime() + 1000 * 60 * 60 * 24 * 30);
    const sessionToken = crypto.randomBytes(32).toString("hex");

    await prisma.session.deleteMany({
      where: {
        userId: user.id,
        expires: {
          lt: now,
        },
      },
    });

    await prisma.session.create({
      data: {
        sessionToken,
        userId: user.id,
        expires,
      },
    });

    const storageState = {
      cookies: [buildCookie(baseUrl, sessionToken, expires)],
      origins: [],
    };

    await fs.mkdir(path.dirname(absoluteOutputPath), { recursive: true });
    await fs.writeFile(
      absoluteOutputPath,
      JSON.stringify(storageState, null, 2),
      "utf8",
    );

    console.log(
      JSON.stringify({
        email: user.email,
        name: user.name,
        outputPath: absoluteOutputPath,
      }),
    );
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
