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
  ".claude/hooks/validate-bash.sh",
  ".claude/rules/coding-style.md",
  ".claude/rules/git-workflow.md",
  ".claude/rules/security.md",
  ".claude/rules/cli-tools.md",
  ".claude/skills/tdd/SKILL.md",
  ".claude/skills/verification/SKILL.md",
  ".claude/skills/brainstorming/SKILL.md",
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
  "scripts/scoped-rules.py",
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

const AVAILABLE_PRESETS = ["unity"];

function copyTree(srcDir, targetDir, installed) {
  if (!fs.existsSync(srcDir)) return;
  const entries = fs.readdirSync(srcDir, { withFileTypes: true });
  for (const entry of entries) {
    const src = path.join(srcDir, entry.name);
    const dst = path.join(targetDir, entry.name);
    if (entry.isDirectory()) {
      copyTree(src, dst, installed);
    } else {
      fs.mkdirSync(path.dirname(dst), { recursive: true });
      fs.copyFileSync(src, dst);
      installed.push(path.relative(targetDir, dst));
    }
  }
}

function init(targetDir, force, preset, lang) {
  const sourceDir = path.resolve(__dirname, "..");
  let templateDir = path.join(sourceDir, "template");
  if (lang === "cn") {
    const cnDir = path.join(sourceDir, "template-cn");
    if (fs.existsSync(cnDir)) {
      templateDir = cnDir;
    } else {
      console.log("Warning: Chinese template not found, falling back to English.");
    }
  }
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

  const langLabel = lang === "cn" ? " (中文)" : "";
  console.log(`\nInstalling claude-autosolve${langLabel} to: ${target}\n`);

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

  // Apply preset overlay (always force — preset overrides core)
  if (preset) {
    const presetDir = path.join(sourceDir, "presets", preset);
    if (!fs.existsSync(presetDir)) {
      console.error(`Error: preset '${preset}' not found at ${presetDir}`);
      process.exit(1);
    }
    console.log(`Applying preset: ${preset}\n`);
    copyTree(presetDir, target, installed);
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
  claude-autosolve init [path] [options]   Install to a project
  claude-autosolve --help                  Show this help

Options:
  --force, -f          Overwrite existing files
  --preset <name>      Apply engine preset (${AVAILABLE_PRESETS.join(", ")})
  --lang <en|cn>       Template language (default: en)
  --help, -h           Show this help message

Examples:
  npx claude-autosolve init                       Install core to current directory
  npx claude-autosolve init --preset unity         Install core + Unity preset
  npx claude-autosolve init --lang cn              Install with Chinese templates
  npx claude-autosolve init ./my-project --force   Install to specified directory
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

  // Parse --preset value
  let preset = null;
  const presetIdx = args.indexOf("--preset");
  if (presetIdx !== -1 && args[presetIdx + 1]) {
    preset = args[presetIdx + 1];
    if (!AVAILABLE_PRESETS.includes(preset)) {
      console.error(`Error: unknown preset '${preset}'. Available: ${AVAILABLE_PRESETS.join(", ")}`);
      process.exit(1);
    }
  }

  // Parse --lang value
  let lang = "en";
  const langIdx = args.indexOf("--lang");
  if (langIdx !== -1 && args[langIdx + 1]) {
    lang = args[langIdx + 1];
    if (!["en", "cn"].includes(lang)) {
      console.error(`Error: unknown lang '${lang}'. Available: en, cn`);
      process.exit(1);
    }
  }

  if (command === "init") {
    const paramValues = [preset, lang].filter(Boolean);
    const targetDir = positional.filter(p => !paramValues.includes(p))[1] || process.cwd();
    init(targetDir, force, preset, lang);
  } else {
    console.error(`Unknown command: ${command}`);
    printHelp();
    process.exit(1);
  }
}

main();
