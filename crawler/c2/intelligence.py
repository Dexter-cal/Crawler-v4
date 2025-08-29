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
        """
        Processes the result data from a plugin against the loaded rules.
        """
        triggered_actions = []
        for rule in self.rules:
            if self._check_condition(rule.get("condition", {}), plugin_name, result):
                action = rule.get("action", {})
                print(f"Rule '{rule.get('name')}' triggered for implant {implant_id}.")
                self._execute_action(action, implant_id, db_session)
                triggered_actions.append(action)
        return triggered_actions

    def _check_condition(self, condition: Dict[str, Any], plugin_name: str, result: Dict[str, Any]) -> bool:
        """
        Checks if the result data meets the rule's condition.
        This is a simple implementation. A real engine would be more complex.
        """
        # Condition must specify the plugin it applies to.
        if condition.get("plugin") != plugin_name:
            return False

        # 'result_not_empty' is a simple condition to check if the plugin returned any data.
        if condition.get("result_not_empty", False):
            # For the evasion plugin, a "finding" means any key other than 'status' exists.
            if plugin_name == 'evasion':
                return any(key != 'status' for key in result.keys())
            # For other plugins, we just check if the result dict is not empty.
            elif result:
                return True

        return False

    def _execute_action(self, action: Dict[str, Any], implant_id: str, db_session):
        """
        Executes the action defined in a rule, e.g., creating a new task.
        """
        action_type = action.get("type")
        if action_type == "task":
            from . import models  # Lazy import to avoid circular dependency

            task_data = action.get("task_details", {})
            command = task_data.get("command")
            args = task_data.get("args", {})

            if not command:
                print("Rule action error: 'task' action is missing 'command'.")
                return

            # Create and add the new task to the database session
            db_task = models.Task(
                implant_id=implant_id,
                command=command,
                args=args,
                status="pending"
            )
            db_session.add(db_task)
            # The calling function will be responsible for committing the session.
            print(f"Action: Queued new task '{command}' for implant {implant_id}.")

        elif action_type == "alert":
            # In a real system, this would go to a logging system, SIEM, or UI.
            print(f"ALERT: {action.get('message', 'No message provided.')} (Implant: {implant_id})")

        else:
            print(f"Unknown action type: {action_type}")
