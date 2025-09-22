#!/usr/bin/env python3
"""
Example usage of the TaskManager module.

This file demonstrates how to use the TaskManager class both in Blender
and standalone environments.
"""

from task_manager import TaskManager

def main():
    """Example usage of TaskManager methods."""
    print("TaskManager Example Usage")
    print("=" * 40)

    # Check if running in Blender environment
    try:
        import bpy
        print("✓ Running in Blender environment")

        # Example: Get active work schedule
        active_schedule = TaskManager.get_active_work_schedule()
        if active_schedule:
            print(f"Active Work Schedule: {active_schedule.Name}")

            # Example: Load task tree
            TaskManager.load_task_tree(active_schedule)
            print("Task tree loaded successfully")

            # Example: Get checked tasks
            checked_tasks = TaskManager.get_checked_tasks()
            print(f"Number of checked tasks: {len(checked_tasks)}")

            # Example: Get task bar list
            task_bars = TaskManager.get_task_bar_list()
            print(f"Tasks with visual bars: {task_bars}")

        else:
            print("No active work schedule found")

    except ImportError:
        print("✗ Not running in Blender environment - using mock data")

        # Example: Standalone usage with mock data
        props = TaskManager.get_work_schedule_props()
        print(f"Mock task bars: {props.task_bars}")

        # Example: Add a task bar (mock operation)
        TaskManager.add_task_bar(123)
        print("Added task bar (mock operation)")

        # Example: Get task bar list (returns empty in standalone)
        task_bars = TaskManager.get_task_bar_list()
        print(f"Task bars: {task_bars}")

if __name__ == "__main__":
    main()