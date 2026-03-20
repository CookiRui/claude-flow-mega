#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

// ============================================================
// File lists (must match install.py)
// ============================================================

const TEMPLATE_ITEMS = [
  "CLAUDE.md",
  "REVIEW.md",
  ".claudeignore",
  ".github/workflows/ci.yml",
  ".claude/constitution.md",
  ".claude/settings.json",
  ".claude/agents/feature-builder.md",
  ".claude/agents/code-reviewer.md",
  ".claude/agents/test-writer.md",
  ".claude/hooks/protect-files.sh",
  ".claude/hooks/reinject-context.sh",
  ".claude/rules/coding-style.md",
  ".claude/rules/git-workflow.md",
  ".claude/rules/security.md",
  ".claude/skills/tdd/SKILL.md",
  ".claude/skills/verification/SKILL.md",
  ".claude/skills/_template/SKILL.md",
  ".claude/skills/_template/references/detail.md",
  ".claude/commands/init-project.md",
  ".claude/commands/feature-plan-creator.md",
  ".claude/commands/bug-fix.md",
  ".claude/commands/deep-task.md",
  ".claude/commands/upgrade.md",
];

const SCRIPT_ITEMS = [
  "scripts/persistent-solve.py",
  "scripts/repo-map.py",
  "scripts/lint-feedback.sh",
];

// ============================================================
// Helpers
// ============================================================

function copyFile(src, dst, force) {
  if (fs.existsSync(dst) && !force) {
    return "skipped";
  }
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
  return "installed";
}

function makeExecutable(filePath) {
  if (process.platform === "win32") return;
  try {
    const stat = fs.statSync(filePath);
    fs.chmodSync(filePath, stat.mode | 0o111);
  } catch (_) {
    // ignore
  }
}

// ============================================================
// Commands
// ============================================================

function init(targetDir, force) {
  const sourceDir = path.resolve(__dirname, "..");
  const templateDir = path.join(sourceDir, "template");
  const target = path.resolve(targetDir);

  if (!fs.existsSync(target) || !fs.statSync(target).isDirectory()) {
    console.error(`Error: target directory does not exist: ${target}`);
    process.exit(1);
  }

  if (!fs.existsSync(templateDir)) {
    console.error(`Error: template directory not found at ${templateDir}`);
    console.error("This package may be corrupted. Try reinstalling.");
    process.exit(1);
  }

  console.log(`\nInstalling claude-autosolve to: ${target}\n`);

  const installed = [];
  const skipped = [];

  // Copy template files
  for (const item of TEMPLATE_ITEMS) {
    const src = path.join(templateDir, item);
    const dst = path.join(target, item);
    if (!fs.existsSync(src)) {
      console.log(`  Warning: source not found: ${src}`);
      continue;
    }
    const result = copyFile(src, dst, force);
    (result === "installed" ? installed : skipped).push(item);
  }

  // Copy script files
  for (const item of SCRIPT_ITEMS) {
    const src = path.join(sourceDir, item);
    const dst = path.join(target, item);
    if (!fs.existsSync(src)) {
      console.log(`  Warning: source not found: ${src}`);
      continue;
    }
    const result = copyFile(src, dst, force);
    (result === "installed" ? installed : skipped).push(item);
  }

  // Make shell scripts executable
  for (const item of installed) {
    if (item.endsWith(".sh")) {
      makeExecutable(path.join(target, item));
    }
  }

  // Print results
  if (installed.length > 0) {
    console.log(`Installed ${installed.length} files:`);
    for (const f of installed) {
      console.log(`  + ${f}`);
    }
  }

  if (skipped.length > 0) {
    console.log(`\nSkipped ${skipped.length} existing files (use --force to overwrite):`);
    for (const f of skipped) {
      console.log(`  ~ ${f}`);
    }
  }

  if (installed.length === 0 && skipped.length === 0) {
    console.log("Nothing to install.");
    return;
  }

  console.log("\nNext steps:");
  console.log(`  cd ${target}`);
  console.log("  claude");
  console.log("  > /init-project");
  console.log("");
  console.log("This will auto-analyze your project and replace all template");
  console.log("placeholders with project-specific configuration.\n");
}

function printHelp() {
  console.log(`
claude-autosolve — Structured cognition + autonomous execution for Claude Code

Usage:
  claude-autosolve init [path] [--force]   Install to a project
  claude-autosolve --help                  Show this help

Options:
  --force, -f    Overwrite existing files
  --help, -h     Show this help message

Examples:
  npx claude-autosolve init                Install to current directory
  npx claude-autosolve init ./my-project   Install to specified directory
  npx claude-autosolve init --force        Overwrite existing files
`);
}

// ============================================================
// CLI
// ============================================================

function main() {
  const args = process.argv.slice(2);
  const flags = args.filter((a) => a.startsWith("-"));
  const positional = args.filter((a) => !a.startsWith("-"));

  if (flags.includes("--help") || flags.includes("-h") || args.length === 0) {
    printHelp();
    process.exit(0);
  }

  const command = positional[0];
  const force = flags.includes("--force") || flags.includes("-f");

  if (command === "init") {
    const targetDir = positional[1] || process.cwd();
    init(targetDir, force);
  } else {
    console.error(`Unknown command: ${command}`);
    printHelp();
    process.exit(1);
  }
}

main();
