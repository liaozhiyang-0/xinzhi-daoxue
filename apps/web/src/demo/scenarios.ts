import type { Intent } from "../api-types.js";

export interface DemoScenario {
  id: string;
  title: string;
  description: string;
  course: string;
  tags: string[];
  exampleInput: string;
  intent: Intent;
  courseId: string;
  caseId: string;
  /** Some fixed demos intentionally use the existing intent route without an enabled scenario contract. */
  runtimeScenarioId?: string | null;
  imageSrc?: string;
  imageName?: string;
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: "faculty_course_copilot_v1",
    title: "教师智能备课",
    description: "把课程目标、课堂节奏和学生差异组织成可执行的教案。",
    course: "模拟电子技术",
    tags: ["任务规划", "课程资料", "教学设计"],
    exampleInput:
      "请为反馈放大器设计一节90分钟课堂：给出教学目标、课堂流程、例题、分层练习和形成性评价，并标出需要教师确认的课程版本或基础假设。",
    intent: "lesson_prep",
    courseId: "AE",
    caseId: "TP-01",
  },
  {
    id: "assessment_diagnosis_v1",
    title: "作业首错诊断",
    description: "沿着学生解题步骤定位首个错误，区分错误传播和最后计算失误。",
    course: "电路理论",
    tags: ["首错定位", "验证", "分层反馈"],
    exampleInput:
      "请检查下面这道电路题的分步解答，定位最早出现的实质错误，说明它如何影响后续步骤，并给出一个不直接替学生做完的验证任务。",
    intent: "assignment_review",
    courseId: "CT",
    caseId: "FE-01",
  },
  {
    id: "student_learning_path_v1",
    title: "学生个性化学习路径",
    description: "结合历史表现、近期变化和前置关系安排下一阶段学习。",
    course: "信号与系统",
    tags: ["学习状态", "前置关系", "阶段计划"],
    exampleInput:
      "根据我的历史表现制定下一阶段学习路径：卷积3/5、傅里叶级数4/5、傅里叶变换2/5、采样1/4、拉普拉斯4/4。请说明优先级、前置知识和每阶段的验证任务。",
    intent: "learning_advice",
    courseId: "SS",
    caseId: "LP-01",
  },
  {
    id: "research_frontier_radar_v1",
    title: "科研前沿证据简报",
    description: "在明确时间和主题边界内整理文献证据、冲突与待核实结论。",
    course: "科研检索",
    tags: ["范围约束", "证据治理", "引用核验"],
    exampleInput:
      "请检索2025年1月至2026年8月医学影像基础模型用于肺结节分割的研究，整理研究问题、方法、证据来源和局限；没有可靠来源支持的定量结论不要补写。",
    intent: "academic_search",
    courseId: "AUTO",
    caseId: "RB-01",
  },
  {
    id: "department_knowledge_governance_v1",
    title: "学院知识库治理",
    description: "处理资料版本、来源、权限、发布、回滚和人工审批边界。",
    course: "课程资产治理",
    tags: ["版本治理", "权限审查", "发布审核"],
    exampleInput:
      "请审查一份课程资料更新：2026版拟替代2025版，但部分来源不明，且资料包含教师备注。请给出版本关系、风险、发布前检查和是否允许面向学生发布的结论。",
    intent: "summarize_knowledge",
    courseId: "AUTO",
    caseId: "KG-01",
  },
  {
    id: "academic_visual_problem_solver_v1",
    title: "模拟电路题图诊断",
    description: "结合电路图判断工作状态、公式适用条件和输出边界。",
    course: "模拟电子技术",
    tags: ["图像理解", "电路求解", "边界验证"],
    exampleInput:
      "请结合随附运算放大器电路图逐步分析：先判断是否处于线性负反馈状态，再说明虚短和虚断能否使用，推导关键节点关系，并指出输出饱和边界、图像读数不确定处和需要人工复核的假设。",
    intent: "solve_problem",
    courseId: "AE",
    caseId: "AC-01",
    runtimeScenarioId: null,
    imageSrc: "/demo-assets/case6-opamp.png",
    imageName: "AC-01_运放结构演示图.png",
  },
];

export const DEFAULT_DEMO_SCENARIO = DEMO_SCENARIOS[0];

export async function loadScenarioImage(scenario: DemoScenario): Promise<File | null> {
  if (!scenario.imageSrc) return null;
  const response = await fetch(scenario.imageSrc);
  if (!response.ok) throw new Error("示例题图片暂时无法读取");
  const blob = await response.blob();
  return new File([blob], scenario.imageName || "question.jpg", {
    type: blob.type || "image/jpeg",
  });
}
