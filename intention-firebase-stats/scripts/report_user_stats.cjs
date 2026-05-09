#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');

function parseArgs(argv) {
  const args = {
    repo: '/Users/Henry/Developer/intention-setting',
    timezone: 'America/New_York',
    json: false,
  };

  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--json') {
      args.json = true;
    } else if (arg === '--repo') {
      args.repo = argv[index + 1];
      index += 1;
    } else if (arg.startsWith('--repo=')) {
      args.repo = arg.slice('--repo='.length);
    } else if (arg === '--timezone') {
      args.timezone = argv[index + 1];
      index += 1;
    } else if (arg.startsWith('--timezone=')) {
      args.timezone = arg.slice('--timezone='.length);
    } else if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return args;
}

function printHelp() {
  console.log(`Usage: report_user_stats.cjs [--repo /path/to/intention-setting] [--timezone America/New_York] [--json]

Read-only aggregate Firebase report for the Intention Setting app.
Default repo: /Users/Henry/Developer/intention-setting
`);
}

function requireFromPublicSite(publicSiteDir, moduleName) {
  const packageJsonPath = path.join(publicSiteDir, 'package.json');
  if (!fs.existsSync(packageJsonPath)) {
    throw new Error(`Missing public-site package.json at ${packageJsonPath}`);
  }

  const publicSiteRequire = createRequire(packageJsonPath);
  try {
    return publicSiteRequire(moduleName);
  } catch (error) {
    throw new Error(
      `Could not require ${moduleName} from ${publicSiteDir}. Install dependencies there first. ${error.message}`
    );
  }
}

function increment(object, key, by = 1) {
  object[key] = (object[key] || 0) + by;
}

function parseTime(value) {
  if (!value) return 0;
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
  if (value && typeof value.toMillis === 'function') return value.toMillis();
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function dateKeyFromOffset(now, offset) {
  const date = new Date(now);
  date.setDate(date.getDate() - offset);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function buildRecentDaySet(now, days) {
  return new Set(Array.from({ length: days }, (_, index) => dateKeyFromOffset(now, index)));
}

function normalizeHistoryEntry(entry) {
  if (!entry || typeof entry !== 'object') return null;

  return {
    totalTimeSpent: Math.max(0, Math.floor(Number(entry.totalTimeSpent) || 0)),
    trackedSiteCount: Math.max(0, Math.floor(Number(entry.trackedSiteCount) || 0)),
  };
}

async function listAllAuthUsers(auth) {
  const users = [];
  let pageToken;

  do {
    const result = await auth.listUsers(1000, pageToken);
    users.push(...result.users);
    pageToken = result.pageToken;
  } while (pageToken);

  return users;
}

async function safeGetCollection(db, collectionName) {
  try {
    return await db.collection(collectionName).get();
  } catch (error) {
    return { docs: [], size: 0, error: error.message || String(error) };
  }
}

async function safeCollectionGroup(db, collectionId) {
  try {
    return await db.collectionGroup(collectionId).get();
  } catch (error) {
    return { docs: [], size: 0, error: error.message || String(error) };
  }
}

async function safeCount(collectionRef) {
  try {
    const snapshot = await collectionRef.count().get();
    return snapshot.data().count;
  } catch {
    return null;
  }
}

function summarizeAuthUsers(authUsers, windows) {
  const authStats = {
    totalUsers: authUsers.length,
    disabledUsers: 0,
    emailVerifiedUsers: 0,
    createdLast1d: 0,
    createdLast7d: 0,
    createdLast30d: 0,
    signedInLast1d: 0,
    signedInLast7d: 0,
    signedInLast30d: 0,
    signedInLast90d: 0,
    neverSignedIn: 0,
    providerCounts: {},
  };

  for (const user of authUsers) {
    if (user.disabled) authStats.disabledUsers += 1;
    if (user.emailVerified) authStats.emailVerifiedUsers += 1;

    const createdAt = parseTime(user.metadata.creationTime);
    const lastSignInAt = parseTime(user.metadata.lastSignInTime);

    if (createdAt >= windows.last1d) authStats.createdLast1d += 1;
    if (createdAt >= windows.last7d) authStats.createdLast7d += 1;
    if (createdAt >= windows.last30d) authStats.createdLast30d += 1;
    if (!lastSignInAt || lastSignInAt === createdAt) authStats.neverSignedIn += 1;
    if (lastSignInAt >= windows.last1d) authStats.signedInLast1d += 1;
    if (lastSignInAt >= windows.last7d) authStats.signedInLast7d += 1;
    if (lastSignInAt >= windows.last30d) authStats.signedInLast30d += 1;
    if (lastSignInAt >= windows.last90d) authStats.signedInLast90d += 1;

    const providers = user.providerData.length
      ? user.providerData.map((provider) => provider.providerId)
      : ['none'];
    for (const provider of providers) increment(authStats.providerCounts, provider);
  }

  return authStats;
}

function summarizeUserDocs(usersSnap, windows, recentDaySets) {
  const firestoreStats = {
    userDocs: usersSnap.size,
    userDocsWithEmail: 0,
    profileSyncedLast7d: 0,
    profileSyncedLast30d: 0,
    usersWithRules: 0,
    totalRules: 0,
    ruleTypeCounts: {},
    usersWithGroups: 0,
    totalGroups: 0,
    usersWithConversationHistory: 0,
    usersWithUsageHistory: 0,
    totalUsageHistoryDays: 0,
    usersWithAnyUsageLast7d: 0,
    usersWithAnyUsageLast30d: 0,
    trackedSiteDaysAllTime: 0,
    trackedUsageSecondsAllTime: 0,
    trackedUsageSecondsLast7d: 0,
    trackedUsageSecondsLast30d: 0,
    trackedUsageSecondsLast90d: 0,
    lastDailyResetLast7d: 0,
    lastDailyResetLast30d: 0,
  };

  for (const doc of usersSnap.docs) {
    const data = doc.data() || {};
    if (typeof data.email === 'string' && data.email.trim()) {
      firestoreStats.userDocsWithEmail += 1;
    }

    const profileSyncedAt = parseTime(data.profileSyncedAt);
    if (profileSyncedAt >= windows.last7d) firestoreStats.profileSyncedLast7d += 1;
    if (profileSyncedAt >= windows.last30d) firestoreStats.profileSyncedLast30d += 1;

    const rules = Array.isArray(data.rules) ? data.rules : [];
    if (rules.length) firestoreStats.usersWithRules += 1;
    firestoreStats.totalRules += rules.length;
    for (const rule of rules) {
      increment(firestoreStats.ruleTypeCounts, rule && rule.type ? String(rule.type) : 'unknown');
    }

    const groups = Array.isArray(data.groups) ? data.groups : [];
    if (groups.length) firestoreStats.usersWithGroups += 1;
    firestoreStats.totalGroups += groups.length;

    const conversationHistory = Array.isArray(data.conversationHistory)
      ? data.conversationHistory
      : [];
    if (conversationHistory.length) firestoreStats.usersWithConversationHistory += 1;

    const resetAt = parseTime(data.lastDailyResetTimestamp);
    if (resetAt >= windows.last7d) firestoreStats.lastDailyResetLast7d += 1;
    if (resetAt >= windows.last30d) firestoreStats.lastDailyResetLast30d += 1;

    const history = data.dailyUsageHistory && typeof data.dailyUsageHistory === 'object'
      ? data.dailyUsageHistory
      : {};
    const historyEntries = Object.entries(history);
    if (historyEntries.length) firestoreStats.usersWithUsageHistory += 1;
    firestoreStats.totalUsageHistoryDays += historyEntries.length;

    let userHasUsageLast7d = false;
    let userHasUsageLast30d = false;

    for (const [dayKey, rawEntry] of historyEntries) {
      const entry = normalizeHistoryEntry(rawEntry);
      if (!entry) continue;

      firestoreStats.trackedUsageSecondsAllTime += entry.totalTimeSpent;
      firestoreStats.trackedSiteDaysAllTime += entry.trackedSiteCount;

      if (recentDaySets.last7.has(dayKey)) {
        firestoreStats.trackedUsageSecondsLast7d += entry.totalTimeSpent;
        if (entry.totalTimeSpent > 0) userHasUsageLast7d = true;
      }
      if (recentDaySets.last30.has(dayKey)) {
        firestoreStats.trackedUsageSecondsLast30d += entry.totalTimeSpent;
        if (entry.totalTimeSpent > 0) userHasUsageLast30d = true;
      }
      if (recentDaySets.last90.has(dayKey)) {
        firestoreStats.trackedUsageSecondsLast90d += entry.totalTimeSpent;
      }
    }

    if (userHasUsageLast7d) firestoreStats.usersWithAnyUsageLast7d += 1;
    if (userHasUsageLast30d) firestoreStats.usersWithAnyUsageLast30d += 1;
  }

  const userDocCount = usersSnap.size || 0;
  return {
    ...firestoreStats,
    trackedUsageHoursAllTime: roundHours(firestoreStats.trackedUsageSecondsAllTime),
    trackedUsageHoursLast7d: roundHours(firestoreStats.trackedUsageSecondsLast7d),
    trackedUsageHoursLast30d: roundHours(firestoreStats.trackedUsageSecondsLast30d),
    trackedUsageHoursLast90d: roundHours(firestoreStats.trackedUsageSecondsLast90d),
    averageRulesPerUserDoc: userDocCount ? round1(firestoreStats.totalRules / userDocCount) : 0,
    averageGroupsPerUserDoc: userDocCount ? round1(firestoreStats.totalGroups / userDocCount) : 0,
  };
}

function summarizeSharing(shareMappingsSnap, privateSnap) {
  const sharingStats = {
    shareIdMappings: shareMappingsSnap.size || 0,
    enabledShareIdMappings: 0,
    privateShareSettingsDocs: privateSnap.size || 0,
    enabledPrivateShareSettingsDocs: 0,
    shareMappingsQueryError: shareMappingsSnap.error || null,
    privateQueryError: privateSnap.error || null,
  };

  for (const doc of shareMappingsSnap.docs || []) {
    if (doc.data()?.enabled === true) sharingStats.enabledShareIdMappings += 1;
  }

  for (const doc of privateSnap.docs || []) {
    if (doc.id === 'shareSettings' && doc.data()?.enabled === true) {
      sharingStats.enabledPrivateShareSettingsDocs += 1;
    }
  }

  return sharingStats;
}

function summarizeBilling(customersCount, subscriptionsSnap) {
  const billingStats = {
    customerDocs: customersCount,
    subscriptionDocs: subscriptionsSnap.size || 0,
    subscriptionStatusCounts: {},
    activeOrTrialingSubscriptions: 0,
    subscriptionQueryError: subscriptionsSnap.error || null,
  };

  for (const doc of subscriptionsSnap.docs || []) {
    const status = String(doc.data()?.status || 'unknown');
    increment(billingStats.subscriptionStatusCounts, status);
    if (status === 'active' || status === 'trialing') {
      billingStats.activeOrTrialingSubscriptions += 1;
    }
  }

  return billingStats;
}

function round1(value) {
  return Math.round(value * 10) / 10;
}

function roundHours(seconds) {
  return round1(seconds / 3600);
}

function printHuman(result) {
  const lines = [
    `Firebase aggregate stats for ${result.projectId}`,
    `As of: ${result.asOf}`,
    `Timezone for usage windows: ${result.timezoneUsedForUsageWindows}`,
    '',
    `Auth users: ${result.auth.totalUsers}`,
    `Verified emails: ${result.auth.emailVerifiedUsers}`,
    `Signed in last 7d / 30d / 90d: ${result.auth.signedInLast7d} / ${result.auth.signedInLast30d} / ${result.auth.signedInLast90d}`,
    `Created last 7d / 30d: ${result.auth.createdLast7d} / ${result.auth.createdLast30d}`,
    '',
    `Firestore user docs: ${result.firestore.userDocs}`,
    `Users with rules / groups: ${result.firestore.usersWithRules} / ${result.firestore.usersWithGroups}`,
    `Total rules / groups: ${result.firestore.totalRules} / ${result.firestore.totalGroups}`,
    `Rule types: ${JSON.stringify(result.firestore.ruleTypeCounts)}`,
    '',
    `Users with usage history: ${result.firestore.usersWithUsageHistory}`,
    `Usage hours all time / 90d / 30d / 7d: ${result.firestore.trackedUsageHoursAllTime} / ${result.firestore.trackedUsageHoursLast90d} / ${result.firestore.trackedUsageHoursLast30d} / ${result.firestore.trackedUsageHoursLast7d}`,
    `Users with any usage last 7d / 30d: ${result.firestore.usersWithAnyUsageLast7d} / ${result.firestore.usersWithAnyUsageLast30d}`,
    '',
    `Enabled public share links: ${result.sharing.enabledShareIdMappings}`,
    `Billing customer docs: ${result.billing.customerDocs}`,
    `Active/trialing subscriptions: ${result.billing.activeOrTrialingSubscriptions}`,
  ];

  const warnings = [
    result.sharing.shareMappingsQueryError && `shareIdMappings query failed: ${result.sharing.shareMappingsQueryError}`,
    result.sharing.privateQueryError && `private collection group query failed: ${result.sharing.privateQueryError}`,
    result.billing.subscriptionQueryError && `subscriptions collection group query failed: ${result.billing.subscriptionQueryError}`,
  ].filter(Boolean);

  if (warnings.length) {
    lines.push('', 'Warnings:', ...warnings.map((warning) => `- ${warning}`));
  }

  console.log(lines.join('\n'));
}

async function main() {
  const args = parseArgs(process.argv);
  process.env.TZ = args.timezone;

  const repoRoot = path.resolve(args.repo);
  const publicSiteDir = path.join(repoRoot, 'public-site');
  const credentialPath = path.join(
    publicSiteDir,
    'scripts',
    'intention-setter-firebase-adminsdk-fbsvc-0449a100a5.json'
  );

  if (!fs.existsSync(credentialPath)) {
    throw new Error(`Missing Firebase admin credential at ${credentialPath}`);
  }

  const admin = requireFromPublicSite(publicSiteDir, 'firebase-admin');
  const serviceAccount = JSON.parse(fs.readFileSync(credentialPath, 'utf8'));

  if (!admin.apps.length) {
    admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
  }

  const db = admin.firestore();
  const auth = admin.auth();
  const now = new Date();
  const nowMs = now.getTime();
  const dayMs = 24 * 60 * 60 * 1000;
  const windows = {
    last1d: nowMs - dayMs,
    last7d: nowMs - 7 * dayMs,
    last30d: nowMs - 30 * dayMs,
    last90d: nowMs - 90 * dayMs,
  };
  const recentDaySets = {
    last7: buildRecentDaySet(now, 7),
    last30: buildRecentDaySet(now, 30),
    last90: buildRecentDaySet(now, 90),
  };

  const [
    authUsers,
    usersSnap,
    shareMappingsSnap,
    privateSnap,
    subscriptionsSnap,
    customersCount,
  ] = await Promise.all([
    listAllAuthUsers(auth),
    db.collection('users').get(),
    safeGetCollection(db, 'shareIdMappings'),
    safeCollectionGroup(db, 'private'),
    safeCollectionGroup(db, 'subscriptions'),
    safeCount(db.collection('customers')),
  ]);

  const result = {
    projectId: serviceAccount.project_id,
    asOf: now.toISOString(),
    repoRoot,
    timezoneUsedForUsageWindows: args.timezone,
    auth: summarizeAuthUsers(authUsers, windows),
    firestore: summarizeUserDocs(usersSnap, windows, recentDaySets),
    sharing: summarizeSharing(shareMappingsSnap, privateSnap),
    billing: summarizeBilling(customersCount, subscriptionsSnap),
  };

  if (args.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    printHuman(result);
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
