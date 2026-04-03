# Module: _root (L1)

Generated: 2026-03-30 | Files: 8 | Symbols: 183

## install.py

- `function` **find_source_dir** L72 (1 refs)
- `function` **detect_presets** L85 (1 refs)
- `function` **copy_tree** L102 (1 refs)
- `function` **install_core** L117 (1 refs)
- `function` **install_preset** L173 (2 refs)
- `function` **print_results** L193 (3 refs)

## scripts/persistent-solve.py

- `class` **Task** L58 (26 refs)
- `class` **TaskDAG** L70 (17 refs)
- `method` **add_task** L76
- `method` **get_ready_tasks** L79 (3 refs)
- `method` **get_parallel_groups** L94 (4 refs)
- `method` **mark_done** L123 (2 refs)
- `method` **mark_failed** L128 (3 refs)
- `method` **has_ready_tasks** L138 (2 refs)
- `method` **all_done** L141 (1 refs)
- `method` **summary** L144 (9 refs)
- `class` **BudgetTracker** L156 (22 refs)
- `method` **record** L166 (8 refs)
- `method` **remaining** L172 (13 refs)
- `method` **can_afford** L176 (5 refs)
- `method` **next_task_budget** L184 (4 refs)
- `method` **summary** L188 (9 refs)
- `function` **ensure_wip_dir** L200 (1 refs)
- `function` **read_wip** L205 (3 refs)
- `function` **parse_wip_status** L214 (1 refs)
- `function` **count_completed_tasks** L236 (2 refs)
- `function` **delete_wip** L243
- `function` **build_first_round_prompt** L293 (1 refs)
- `function` **build_resume_prompt** L302 (1 refs)
- `function` **_parse_claude_json** L324 (1 refs)
- `function` **run_claude_session** L374 (11 refs)
- `function` **build_clarify_prompt** L436 (5 refs)
- `function` **build_plan_prompt** L471 (2 refs)
- `function` **parse_dag_response** L511 (8 refs)
- `function` **clarify_goal** L553 (10 refs)
- `function` **plan_dag** L630 (1 refs)
- `function` **build_task_prompt** L649 (1 refs)
- `function` **execute_task** L677 (2 refs)
- `function` **execute_parallel** L689 (1 refs)
- `function` **execute_dag** L714 (1 refs)
- `function` **persistent_solve** L755 (1 refs)
- `function` **_run_dag_mode** L798 (1 refs)
- `function` **_run_legacy_mode** L869 (1 refs)

## scripts/repo-map.py

- `function` **load_config** L116 (3 refs)
- `function` **detect_modules** L128 (13 refs)
- `function` **classify_file_to_module** L185 (5 refs)
- `function` **scan_files** L214 (5 refs)
- `function` **extract_symbols** L230 (4 refs)
- `function` **count_references_scoped** L262 (2 refs)
- `function` **load_state** L286 (2 refs)
- `function` **save_state** L298 (1 refs)
- `function` **get_current_commit** L306 (1 refs)
- `function` **get_changed_files** L320 (3 refs)
- `function` **detect_primary_language** L357 (2 refs)
- `function` **compute_cross_module_refs** L377 (1 refs)
- `function` **generate_l0** L416 (2 refs)
- `function` **generate_l1** L465 (2 refs)
- `function` **build_module_data** L499 (2 refs)
- `function` **build_layered_map** L559 (1 refs)
- `function` **build_flat_map** L676 (1 refs)
- `function` **format_flat_json** L701 (1 refs)
- `function` **format_flat_markdown** L705 (1 refs)

## scripts/scope-loader.py

- `function` **load_config** L56 (3 refs)
- `function` **detect_modules** L68 (13 refs)
- `function` **classify_file_to_module** L110 (5 refs)
- `function` **get_affected_files_from_git** L129 (1 refs)
- `function` **get_affected_modules** L155 (2 refs)
- `function` **find_root_constitutions** L173 (1 refs)
- `function` **find_root_rules** L182 (1 refs)
- `function` **find_module_constitutions** L193 (1 refs)
- `function` **find_module_rules** L208 (1 refs)
- `function` **resolve_all** L225 (1 refs)
- `function` **format_inject** L256 (1 refs)
- `function` **format_json_output** L293 (1 refs)

## scripts/scoped-rules.py

- `function` **detect_modules** L45 (13 refs)
- `function` **affected_modules** L94 (20 refs)
- `function` **load_module_constitution** L135 (3 refs)
- `function` **load_module_rules** L168 (3 refs)
- `function` **merge_rules** L212 (3 refs)
- `function` **get_scoped_rules** L241 (3 refs)
- `function` **get_changed_files_from_git** L293 (1 refs)
- `function` **format_json** L325 (1 refs)
- `function` **format_markdown** L330 (1 refs)

## tests/test_persistent_solve.py

- `class` **TestTaskDAG** L31
- `method` **_make_tasks** L33 (5 refs)
- `method` **test_get_ready_tasks_initial** L43
- `method` **test_get_ready_tasks_after_done** L48
- `method` **test_mark_failed_retries** L55
- `method` **test_has_ready_tasks** L65
- `method` **test_all_done** L73
- `method` **test_parallel_groups_no_conflict** L80
- `method` **test_parallel_groups_with_conflict** L92
- `method` **test_parallel_groups_empty_files_sequential** L104
- `method` **test_single_task_parallel** L118
- `class` **TestBudgetTracker** L131
- `method` **test_initial_state** L133
- `method` **test_record_and_remaining** L138
- `method` **test_budget_exhausted** L144
- `method` **test_next_task_budget_capped** L150
- `method` **test_thread_safety** L155
- `class` **TestParseDagResponse** L174
- `method` **test_valid_json** L176
- `method` **test_no_json_fence_fallback** L192
- `method` **test_invalid_json_fallback** L197
- `method` **test_non_array_json_fallback** L202
- `method` **test_empty_response_fallback** L207
- `class` **TestBuildClarifyPrompt** L216
- `method` **test_contains_goal** L218
- `method` **test_asks_for_json** L222
- `class` **TestClarifyGoal** L233
- `method` **_mock_session** L235 (6 refs)
- `method` **test_clear_goal_passes_through** L250
- `method` **test_ambiguous_goal_asks_user** L258
- `method` **test_ambiguous_goal_accept_defaults** L271
- `method` **test_user_aborts** L284
- `method` **test_unparseable_response_passes_through** L294
- `method` **test_eof_on_input_passes_through** L305
- `method` **test_budget_recorded** L316

## tests/test_repo_map.py

- `class` **TestScanFiles** L18
- `method` **test_scan_finds_python_files** L39
- `method` **test_scan_with_subdir** L46
- `method` **test_scan_nonexistent_subdir_returns_empty** L52
- `class` **TestExtractSymbols** L57
- `method` **test_extract_class_and_functions** L73
- `method` **test_symbols_have_required_fields** L80
- `method` **test_noise_names_are_skipped** L88
- `class` **TestDetectModules** L101
- `method` **test_detects_source_directories_as_modules** L123
- `method` **test_excludes_non_module_dirs** L130
- `method` **test_includes_root_pseudo_module** L136
- `method` **test_explicit_config_modules** L142
- `class` **TestClassifyFileToModule** L157
- `method` **test_classify_file_in_module** L167
- `method` **test_classify_root_file** L173
- `method` **test_classify_unknown_path_falls_back_to_root** L179
- `method` **test_classify_without_root_returns_unclassified** L186
- `class` **TestBuildFlatMap** L197
- `method` **test_build_returns_expected_structure** L208
- `class` **TestBuildModuleData** L216
- `method` **test_builds_data_for_all_modules** L236
- `method` **test_only_modules_filter** L245
- `class` **TestGenerateL0** L253
- `method` **test_l0_contains_module_table** L256
- `method` **test_l0_shows_cross_refs** L272
- `class` **TestGenerateL1** L285
- `method` **test_l1_shows_symbols_with_lines** L288
- `method` **test_l1_groups_by_file** L300
- `class` **TestGetChangedFiles** L311
- `method` **test_returns_none_without_last_commit** L315
- `method` **test_collects_from_multiple_git_commands** L321
- `method` **side_effect** L323 (3 refs)
- `method` **test_returns_none_on_git_failure** L341
- `class` **TestStateManagement** L347
- `method` **test_load_state_returns_empty_when_no_file** L353
- `method` **test_save_and_load_roundtrip** L357
- `method` **test_load_config_returns_defaults** L363
- `class` **TestFlatMarkdownFormat** L369
- `method` **test_format_includes_header** L372
- `class` **TestDetectPrimaryLanguage** L387
- `method` **test_python_detected** L390
- `method` **test_empty_symbols_returns_dash** L398

## tests/test_scoped_rules.py

- `class` **TestDetectModules** L17
- `method` **test_detect_modules_finds_scoped_dirs** L31
- `method` **test_detect_modules_includes_root** L38
- `method` **test_detect_modules_returns_relative_paths** L43
- `class` **TestAffectedModules** L50
- `method` **test_files_in_module_a_affect_module_a** L60
- `method` **test_files_in_root_affect_root** L67
- `method` **test_files_in_non_module_dir_affect_root** L73
- `method` **test_empty_changed_files_returns_empty** L80
- `class` **TestLoadModuleRules** L85
- `method` **test_load_root_rules** L115
- `method` **test_load_module_rules** L121
- `method` **test_load_module_constitution** L126
- `method` **test_load_root_constitution** L131
- `class` **TestRulePriority** L137
- `method` **test_module_rules_override_root_on_conflict** L140
- `method` **test_non_conflicting_rules_are_both_included** L153
- `method` **test_empty_module_rules_returns_root** L163
- `class` **TestScopedRulesForDiff** L171
- `method` **test_get_scoped_rules_for_module_change** L197
- `method` **test_get_scoped_rules_for_root_change** L207
- `method` **test_output_format_is_json_serializable** L215
