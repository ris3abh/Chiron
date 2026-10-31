# Phase 1 baseline: the untouched base app (v1.5.3)

The base app's test suite as it was before any Chiron change, so the Phase 1 report can tell failures that were already there from failures Phase 1 introduced.

## How it was run

- Source: the upstream base at v1.5.3 (commit `dac5448`), in a separate git worktree. Its test file `test_chiron.py` is now `test_chiron.py`; names below use the new name.
- Command: `python3 -m unittest discover -s tests -v`, with the upstream host-UI guard variables unset (now `CHIRON_VM` / `CHIRON_ALLOW_HOST_UI`), so the host guard skipped the tests that drive real apps.
- Machine: macOS 15.3.2, Python 3.14.8, Command Line Tools with Swift 6.1. That toolchain is broken: its compiler does not match its SDK (`swiftlang-6.1.0.110.21` against an SDK built with `110.5`), and even a hello-world `swiftc` fails with `redefinition of module 'SwiftBridging'`. No Xcode is installed.
- Date: 2026-10-28. Took 58 minutes; nearly all of it goes on tests that try to compile Swift.

## Result

**844 tests: 98 failures, 6 errors, 23 skipped.**

| Cause | Count |
|---|---|
| Swift does not compile on this Mac (toolchain mismatch) | 100 |
| System-prompt budget over its limit | 4 |

### System-prompt budget (4)

The base app's prompt is 11,103 characters against a 10,000 limit (10,122 against 10,050 in `test_screen_draw`, which swaps in the installed path).
Part of this depends on where the repo is checked out: the prompt repeats the full path of the script, and this worktree's path is about 120 characters long.
Phase 1 removes the agent hand-off rules from the prompt, so these should pass after Phase 1 in any checkout. If they don't, that is a Phase 1 problem.

- `test_chiron.WatchAndBudgetTests.test_prompt_stays_under_budget` (FAIL)
- `test_screen_draw.DrawingTests.test_disabled_tool_and_prompt_budget` (FAIL)
- `test_universal.UniversalTests.test_general_method_and_prompt_budget` (FAIL)
- `test_workflows.WorkflowTests.test_only_matching_procedure_enters_prompt_and_remember_waits_for_confirmation` (FAIL)

### Swift toolchain (100)

These fail or error in setup because `swiftc` cannot build anything on this Mac. They say nothing about the code. They must be rerun on macOS 26 with Xcode 26, or in CI (`.github/workflows/dev-dmg.yml`).

- `test_agent_math_page.AgentMathPageTests.test_agent_answers_render_markdown_and_math_like_the_box` (FAIL)
- `test_agent_times_page.AgentTimesPageTests.test_each_agent_shows_its_start_today_yesterday_or_older` (FAIL)
- `test_agents_native.AgentNativeTests.test_badge_counts_only_working_agents_but_restart_guard_keeps_live_work` (FAIL)
- `test_agents_native.AgentNativeTests.test_card_flight_placement_and_reduced_motion` (FAIL)
- `test_agents_native.AgentNativeTests.test_click_expand_is_smooth_and_resizes_once_per_change` (FAIL)
- `test_agents_native.AgentNativeTests.test_complete_app_compiles_and_native_selftest` (FAIL)
- `test_agents_native.AgentNativeTests.test_crashed_supervisor_restarts_without_its_half_line` (FAIL)
- `test_agents_native.AgentNativeTests.test_move_shortcut_is_held_only_while_movable_and_keeps_focus` (FAIL)
- `test_agents_native.AgentNativeTests.test_offered_agents_start_without_a_card` (FAIL)
- `test_agents_native.AgentNativeTests.test_pause_stops_every_live_agent_queued_first` (FAIL)
- `test_agents_native.AgentNativeTests.test_real_click_opens_agent_view_and_close_restores_the_shelf` (FAIL)
- `test_agents_native.AgentNativeTests.test_real_return_is_captured_only_for_an_actionable_card` (FAIL)
- `test_agents_native.AgentNativeTests.test_shelf_hover_fade_focus_safe_ping_and_screen_lease` (FAIL)
- `test_chiron.BoxLookTests.test_box_size_and_read_aloud` (FAIL)
- `test_audio_native.AudioNativeTests.test_best_installed_english_voice_prefers_quality_then_region` (FAIL)
- `test_audio_native.AudioNativeTests.test_device_choice_falls_back_without_opening_bluetooth` (FAIL)
- `test_audio_native.AudioNativeTests.test_quiet_audio_restores_release_and_cancel` (FAIL)
- `test_audio_native.AudioNativeTests.test_saved_voice_and_unavailable_voice_fallback` (FAIL)
- `test_audio_native.AudioNativeTests.test_say_voice_list_parser_handles_spaces_and_rejects_unknown_names` (FAIL)
- `test_bg_send_native.BackgroundSendNativeTests` (ERROR)
- `test_box_page.BoxPageTests.test_box_on_real_webkit` (FAIL)
- `test_box_page.BoxPageTests.test_picker_renders_answers_and_accepts_spoken_other` (FAIL)
- `test_boxsize.BoxSizeTests.test_saved_width_and_frame_fit_current_screen` (FAIL)
- `test_calendar.CalendarNativeTests.test_eventkit_logic_with_fake_store` (FAIL)
- `test_conversation_rename_page.ConversationRenamePageTests.test_chats_share_rename_and_stay_off_the_shelf` (FAIL)
- `test_conversation_rename_page.ConversationRenamePageTests.test_rename_keyboard_buttons_live_updates_and_selected_identity` (FAIL)
- `test_dictation.DictationNativeTests.test_delivery_retries_only_a_proven_failure_and_keeps_failed_text` (FAIL)
- `test_dictation.DictationNativeTests.test_fn_alone_ignores_arrow_flags_and_yields_to_fn_key_chords` (FAIL)
- `test_dictation.DictationNativeTests.test_fn_and_modifier_only_shortcuts_use_flags_events` (FAIL)
- `test_dictation.DictationNativeTests.test_long_dictation_rollover_stitches_overlap_without_doubling` (FAIL)
- `test_dictation.DictationNativeTests.test_overlay_states_follow_release_done_fallback_fail_and_cancel` (FAIL)
- `test_dictation.DictationNativeTests.test_paste_borrows_the_clipboard_and_restores_every_type` (FAIL)
- `test_dictation.DictationNativeTests.test_pill_over_a_box_that_must_stay_gives_the_box_back` (FAIL)
- `test_dictation.DictationNativeTests.test_selection_is_replaced_only_while_original_app_stays_front` (FAIL)
- `test_dictation.DictationNativeTests.test_verbatim_skips_ai_cleanup_uses_one_call_and_cancel_drops_result` (FAIL)
- `test_dictation_data.DictationDataTests.test_corrections_are_single_words_and_reject_rewrites` (FAIL)
- `test_dictation_data.DictationDataTests.test_learned_fix_swaps_the_heard_word_until_forgotten` (FAIL)
- `test_dictation_data.DictationDataTests.test_private_bounded_history_stats_and_dictionary` (FAIL)
- `test_feedback_native.FeedbackNativeTests.test_failed_worker_clears_url_and_reports_latest_error_without_crashing` (FAIL)
- `test_fixtures.FixtureTests.test_box_contrast_fixture` (FAIL)
- `test_fixtures.FixtureTests.test_main_overlay_fixture` (FAIL)
- `test_fixtures.FixtureTests.test_mock_bridge_fixtures` (FAIL)
- `test_fixtures.FixtureTests.test_timer_row_fixture` (FAIL)
- `test_hands.HandsTests.test_background_command_key_runs_its_exact_menu_item` (FAIL)
- `test_hands.HandsTests.test_main_permission_allow_waits_for_grant_and_stops_on_cancel` (FAIL)
- `test_hands.HandsTests.test_only_plain_keys_into_background_web_content_are_authenticated` (FAIL)
- `test_hands_native.NativeHandsTests` (ERROR)
- `test_ideas.IdeaTests.test_once_a_day_after_a_day_without_an_ask_and_never_when_off` (FAIL)
- `test_main_thread.MainThreadTests.test_activation_returns_without_waiting_and_times_out` (FAIL)
- `test_main_thread.MainThreadTests.test_archive_serializes_batched_writes_off_main_and_reports_errors` (FAIL)
- `test_main_thread.MainThreadTests.test_mic_serializes_sessions_and_ignores_cancelled_starts` (FAIL)
- `test_main_thread.MainThreadTests.test_permission_refresh_deduplicates_pending_probes` (FAIL)
- `test_meeting_bridge.MeetingBridgeTests.test_prep_queue_edits_and_stop_with_fake_workers` (FAIL)
- `test_meeting_native.MeetingNativeTests.test_call_debounce_and_calendar_priority` (FAIL)
- `test_meeting_native.MeetingNativeTests.test_native_journal_append_and_private_atomic_export` (FAIL)
- `test_meeting_native.MeetingNativeTests.test_saved_frames_restore_clamp_and_fallback` (FAIL)
- `test_meeting_native.MeetingNativeTests.test_system_and_microphone_samples_use_separate_feeds` (FAIL)
- `test_miniscreen_native.MiniScreenNativeTests` (ERROR)
- `test_native.NativeTests.test_calendar_dismissal_and_updates_preserve_open_meeting` (FAIL)
- `test_native.NativeTests.test_final_words_after_live_action_preserve_raw_remainder` (FAIL)
- `test_native.NativeTests.test_focus_guard_covers_main_asks_and_fast_work` (FAIL)
- `test_native.NativeTests.test_live_worker_cancellation_revision_and_pipe_drain` (FAIL)
- `test_native.NativeTests.test_meeting_size_stays_on_small_and_secondary_displays` (FAIL)
- `test_native.NativeTests.test_memory_receipts_fall_through_when_drawing_parser_rejects_them` (FAIL)
- `test_native.NativeTests.test_page_calls_skip_values_json_cannot_hold` (FAIL)
- `test_native.NativeTests.test_replace_checks_original_text_range_and_app` (FAIL)
- `test_native.NativeTests.test_shortcut_states_and_recording_limit` (FAIL)
- `test_native.NativeTests.test_typing_requires_a_zero_length_caret` (FAIL)
- `test_native.NativeTests.test_voice_focus_becomes_the_background_guard_target` (FAIL)
- `test_onboarding_page.OnboardingPageTests` (ERROR)
- `test_prefs_native.PrefsNativeTests.test_all_windows_follow_sharing_preference` (FAIL)
- `test_prefs_native.PrefsNativeTests.test_dictation_shortcut_defaults_to_fn_but_keeps_any_choice` (FAIL)
- `test_prefs_native.PrefsNativeTests.test_retired_settings_keep_saved_values_without_rewriting_disk` (FAIL)
- `test_prefs_native.PrefsNativeTests.test_settings_are_private_and_usage_counts_final_rows` (FAIL)
- `test_prefs_native.PrefsNativeTests.test_unwritable_settings_keep_the_old_value` (FAIL)
- `test_replay_native.ReplayNativeTests.test_menu_success_has_no_post_press_accessibility_queries` (FAIL)
- `test_routing_native.RoutingPreferencesTests.test_native_migration_matches_brain_and_persists_on_next_write` (FAIL)
- `test_routing_native.RoutingPreferencesTests.test_voice_setting_bridge_accepts_migrated_choices` (FAIL)
- `test_screen_draw.DrawingAnchorTests.test_ids_keep_identity_across_expected_value_changes` (FAIL)
- `test_screen_draw.GuideGeometryTests.test_marks_and_callouts_stay_clear_of_targets` (FAIL)
- `test_screen_draw.NativeDrawingTests.test_native_drawings_and_fixture_screenshots` (FAIL)
- `test_screen_draw.NativeDrawingTests.test_product_typechecks` (ERROR)
- `test_selection.SelectionTests.test_capture_is_async_and_cancelled_or_stale_results_are_ignored` (FAIL)
- `test_selection.SelectionTests.test_paste_rechecks_target_cancellation_and_clipboard_ownership` (FAIL)
- `test_selection.SelectionTests.test_typing_capture_accepts_empty_fields_but_never_secure_fields` (FAIL)
- `test_settings_page.SettingsPageTests` (ERROR)
- `test_shelf_page.ShelfPageTests.test_a_finish_opens_its_own_chip_even_on_a_minimized_shelf` (FAIL)
- `test_shelf_page.ShelfPageTests.test_a_finish_pops_open_then_folds_back_after_four_seconds_unless_held` (FAIL)
- `test_shelf_page.ShelfPageTests.test_a_finish_under_the_pointer_waits_and_each_agent_of_one_ask_lands_on_its_orb` (FAIL)
- `test_shelf_page.ShelfPageTests.test_agents_started_together_all_show_then_fold_after_four_seconds_unless_held` (FAIL)
- `test_shelf_page.ShelfPageTests.test_click_opens_in_place_then_the_view_and_every_control_shows_in_every_state` (FAIL)
- `test_shelf_page.ShelfPageTests.test_finished_agents_on_the_real_webkit_shelf` (FAIL)
- `test_shelf_page.ShelfPageTests.test_shelf_layers_never_overlap_and_controls_answer_the_pointer` (FAIL)
- `test_swift_review_fixes.SwiftReviewFixTests.test_fn_key_match_is_exact_and_modifier_prefixes_conflict` (FAIL)
- `test_swift_review_fixes.SwiftReviewFixTests.test_hidden_rewrite_keeps_its_target` (FAIL)
- `test_swift_review_fixes.SwiftReviewFixTests.test_long_step_callout_starts_at_its_first_words` (FAIL)
- `test_swift_review_fixes.SwiftReviewFixTests.test_shelf_follow_keeps_side_offsets` (FAIL)
- `test_swift_review_fixes.SwiftReviewFixTests.test_window_target_reports_a_visible_unfocused_window` (FAIL)
- `test_telemetry.TelemetryTests.test_swift_reports_only_unreported_process_deaths` (FAIL)
- `test_web_frames_page.WebFramesPageTests.test_another_sites_form_frame_is_named_with_where_it_is_and_how_to_reach_it` (FAIL)

## Using this in the Phase 1 report

Compare by test name against the full verbose output of the Phase 1 run:

1. **Already failing:** in this list and still failing. Tests deleted together with a removed feature (agents, meetings, ideas, telemetry, MiniScreen) are listed separately as removed, not as fixed.
2. **Fixed by Phase 1:** in this list and now passing.
3. **Introduced by Phase 1:** failing now but not in this list. This must be zero.
