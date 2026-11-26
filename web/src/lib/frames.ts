export type Frame = {
  idx: number;
  angles: Record<string, number>;
  keypoints?: Record<string, unknown>;
  nao_angles?: number[];
  pose_name?: string;
};

// Frame as returned by server, field names differ between versions
export type RawFrame = {
  idx?: number;
  index?: number;
  frame_index?: number;
  joint_values?: Record<string, number>;
  angles?: Record<string, number>;
  joints?: Record<string, number>;
  joint_angles?: Record<string, number>;
  keypoints?: Record<string, unknown> & { pose_name?: string };
  nao_angles?: number[];
  pose_name?: string;
  poseName?: string;
};

const NAO_JOINT_NAMES = [
  "LShoulderPitch", "LShoulderRoll", "LElbowRoll", "LElbowYaw", "LWristYaw",
  "RShoulderPitch", "RShoulderRoll", "RElbowRoll", "RElbowYaw", "RWristYaw",
  "LHipRoll", "LHipPitch", "LKneePitch", "LAnklePitch", "LAnkleRoll",
  "RHipRoll", "RHipPitch", "RKneePitch", "RAnklePitch", "RAnkleRoll",
  "HeadYaw", "HeadPitch",
];

// Named angles, or built from nao_angles array when server sends none
export function normalizeFrame(frame: RawFrame, position: number): Frame {
  let angles = frame.joint_values ?? frame.angles ?? frame.joints ?? frame.joint_angles ?? {};
  if (Object.keys(angles).length === 0 && Array.isArray(frame.nao_angles)) {
    angles = Object.fromEntries(frame.nao_angles.map((value, j) => [NAO_JOINT_NAMES[j] ?? `j${j}`, value]));
  }
  return {
    idx: frame.idx ?? frame.index ?? frame.frame_index ?? position,
    angles,
    keypoints: frame.keypoints,
    nao_angles: frame.nao_angles,
    pose_name: frame.pose_name ?? frame.poseName ?? frame.keypoints?.pose_name,
  };
}

// Joint range of motion over all frames, prompt input for LLM
export function motionSummary(frames: Frame[]) {
  const ranges: Record<string, { min: number; max: number }> = {};
  for (const frame of frames) {
    for (const [joint, value] of Object.entries(frame.angles)) {
      const range = ranges[joint] ??= { min: value, max: value };
      range.min = Math.min(range.min, value);
      range.max = Math.max(range.max, value);
    }
  }
  const joints = Object.entries(ranges)
    .map(([joint, { min, max }]) => `${joint}: ${(max - min).toFixed(2)} rad`)
    .join(", ");
  return `Exercise has ${frames.length} keyframes. Joint range-of-motion: ${joints}.`;
}
