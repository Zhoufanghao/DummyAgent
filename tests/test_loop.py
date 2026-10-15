"""离线验证逐步工具决策和跨用户轮历史；不调用模型或真实 Bash。"""
import unittest

from test_interactive import answer, run_agent, tool_answer


class LoopTests(unittest.TestCase):
    def test_v4_uses_each_observation_for_next_decision(self):
        result = run_agent(4, ["先加再乘", "解释上次答案"],
                           [tool_answer("fixture-first"),
                            tool_answer("fixture-second", arguments='{"expression":"5*3"}'),
                            answer("15"), answer("上次是15")])
        self.assertEqual(len(result.requests), 4)
        self.assertEqual(result.requests[1]["messages"][-1],
                         {"role": "tool", "tool_call_id": "fixture-first", "content": "5"})
        self.assertEqual(result.requests[2]["messages"][-1],
                         {"role": "tool", "tool_call_id": "fixture-second", "content": "15"})
        self.assertEqual(result.requests[3]["messages"][-2], {"role": "assistant", "content": "15"})
        self.assertTrue(all("tools" in request for request in result.requests))

    def test_v5_uses_bash_observations_then_accepts_another_task(self):
        result = run_agent(5, ["查看数据", "继续查看"],
                           [tool_answer("fixture-bash-one", "bash", '{"command":"cat data/temperature.csv"}'),
                            tool_answer("fixture-bash-two", "bash", '{"command":"ls"}'),
                            answer("数据已读取"), answer("继续回答")], bash_output="fixture stdout")
        self.assertEqual(len(result.requests), 4)
        self.assertEqual([call.args[0] for call in result.bash.call_args_list], ["cat data/temperature.csv", "ls"])
        self.assertEqual(result.requests[1]["messages"][-1],
                         {"role": "tool", "tool_call_id": "fixture-bash-one", "content": "fixture stdout"})
        self.assertEqual(result.requests[2]["messages"][-1]["tool_call_id"], "fixture-bash-two")
        self.assertEqual(result.requests[3]["messages"][-2]["content"], "数据已读取")

    def test_v4_has_no_fixed_100_round_stop(self):
        replies = [tool_answer(f"fixture-{index}") for index in range(101)] + [answer("完成")]
        result = run_agent(4, ["重复计算"], replies)
        self.assertEqual(len(result.requests), 102)
        self.assertIn("完成", result.output)


if __name__ == "__main__":
    unittest.main()
