// Slovak labels of robot pose commands
export const POSE_LABELS: Record<string, string> = {
  wave:        "Zamávaj",
  stand:       "Stoj",
  sit:         "Sed",
  hands_up:    "Ruky hore",
  t_pose:      "T-Póza",
  bow:         "Úklon",
  crouch:      "Drep",
  point_right: "Ukáž vpravo",
  point_left:  "Ukáž vľavo",
};

export const poseLabel = (name: string) => POSE_LABELS[name] ?? name;
