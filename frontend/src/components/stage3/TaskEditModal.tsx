"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { TaskExtraction, TaskActivity, TaskStep } from "@/lib/types";

interface TaskEditModalProps {
  open: boolean;
  onClose: () => void;
  taskExtraction: TaskExtraction;
  onSave: (updatedExtraction: TaskExtraction) => void;
  targetHours: number;
}

export function TaskEditModal({
  open,
  onClose,
  taskExtraction,
  onSave,
  targetHours
}: TaskEditModalProps) {
  const [activities, setActivities] = useState<TaskActivity[]>(taskExtraction.activities);

  const calculateTotalHours = () => {
    return activities.reduce((total, activity) => {
      return total + activity.steps.reduce((actTotal, step) => {
        const factor = step.reusability === "full" ? 0 : step.reusability === "partial" ? 0.5 : 1;
        return actTotal + (step.weight_hours * factor);
      }, 0);
    }, 0);
  };

  const totalHours = calculateTotalHours();
  const isValid = Math.abs(totalHours - targetHours) < 1;

  const handleStepChange = (
    activityIdx: number,
    stepIdx: number,
    field: keyof TaskStep,
    value: any
  ) => {
    const newActivities = [...activities];
    newActivities[activityIdx].steps[stepIdx] = {
      ...newActivities[activityIdx].steps[stepIdx],
      [field]: value
    };
    setActivities(newActivities);
  };

  const handleSave = () => {
    onSave({
      ...taskExtraction,
      activities,
      total_net_hours: totalHours,
      verification_passed: isValid,
      extraction_status: "complete"
    });
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent style={{ maxWidth: "800px", maxHeight: "80vh", overflow: "auto" }}>
        <DialogHeader>
          <DialogTitle>Edit Task Breakdown</DialogTitle>
        </DialogHeader>

        {/* Hour Sum Summary */}
        <div style={{
          padding: "12px",
          background: isValid ? "var(--c-green-bg)" : "var(--c-amber-bg)",
          borderRadius: "8px",
          marginBottom: "16px"
        }}>
          <div style={{ fontSize: "14px", fontWeight: 600 }}>
            Total: {totalHours.toFixed(1)}h / {targetHours}h
            {isValid ? " ✓" : ` (${(totalHours - targetHours).toFixed(1)}h ${totalHours > targetHours ? 'over' : 'under'})`}
          </div>
        </div>

        {/* Activities */}
        {activities.map((activity, actIdx) => (
          <div key={actIdx} style={{ marginBottom: "24px" }}>
            <Label style={{ fontSize: "16px", fontWeight: 600, marginBottom: "12px", display: "block" }}>
              {activity.name}
            </Label>

            {activity.steps.map((step, stepIdx) => (
              <div key={stepIdx} style={{
                display: "grid",
                gridTemplateColumns: "2fr 100px 120px",
                gap: "8px",
                marginBottom: "8px",
                alignItems: "center"
              }}>
                <Input
                  value={step.description}
                  onChange={(e) => handleStepChange(actIdx, stepIdx, "description", e.target.value)}
                  style={{ fontSize: "13px" }}
                />
                <Input
                  type="number"
                  value={step.weight_hours}
                  onChange={(e) => handleStepChange(actIdx, stepIdx, "weight_hours", parseFloat(e.target.value) || 0)}
                  style={{ fontSize: "13px" }}
                  step="0.5"
                />
                <Select
                  value={step.reusability}
                  onValueChange={(value) => handleStepChange(actIdx, stepIdx, "reusability", value as "none" | "partial" | "full")}
                >
                  <SelectTrigger style={{ fontSize: "13px" }}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None (100%)</SelectItem>
                    <SelectItem value="partial">Partial (50%)</SelectItem>
                    <SelectItem value="full">Full (0%)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
        ))}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "24px" }}>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!isValid}>
            Save Changes
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
