import { wordPattern } from "@/lib/text";

// Pose command from robot API
export type PoseCommand = { name: string };

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

// Spoken forms of pose commands, Slovak and English
const POSE_ALIASES: [string, string][] = [
  ["drep", "crouch"],
  ["úklon", "bow"], ["uklon", "bow"],
  ["zamávaj", "wave"], ["zamavaj", "wave"], ["zamávajte", "wave"],
  ["stoj", "stand"],
  ["sed", "sit"], ["sadni", "sit"],
  ["ruky hore", "hands_up"],
  ["t-póza", "t_pose"], ["t póza", "t_pose"], ["tpóza", "t_pose"], ["t poza", "t_pose"],
  ["ukáž vpravo", "point_right"], ["ukaz vpravo", "point_right"],
  ["ukáž vľavo", "point_left"], ["ukaz vlavo", "point_left"],
  ["crouch", "crouch"], ["bow", "bow"], ["wave", "wave"], ["stand", "stand"],
  ["sit", "sit"], ["hands up", "hands_up"], ["t pose", "t_pose"], ["t-pose", "t_pose"],
  ["point right", "point_right"], ["point left", "point_left"],
];

// Pose commands in spoken order, repeats kept, aliases matched as whole words
export function findPoses(text: string): string[] {
  const found: { at: number; pose: string }[] = [];
  for (const [alias, pose] of POSE_ALIASES) {
    for (const match of text.matchAll(wordPattern(alias))) found.push({ at: match.index, pose });
  }
  return found.sort((a, b) => a.at - b.at).map(({ pose }) => pose);
}
