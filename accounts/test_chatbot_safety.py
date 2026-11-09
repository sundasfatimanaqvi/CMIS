from unittest import mock

from django.test import SimpleTestCase

from . import chatbot


class EmergencyDetectionTests(SimpleTestCase):
    def test_english_variants(self):
        for text in ["my father is clutching his chest", "she is not waking up", "I can't catch my breath",
                     "he swallowed a lot of pills", "a snake bit him", "coughing up blood"]:
            self.assertTrue(chatbot.is_emergency(text), text)

    def test_roman_urdu_and_urdu(self):
        for text in ["mujhe saans nahi aa rahi", "seene mein dard hai", "bachay ne zeher pi liya", "khoon ruk nahi raha",
                     "مجھے سانس نہیں آ رہی", "سینے میں شدید درد ہے", "بچی بے ہوش ہو گئی ہے"]:
            self.assertTrue(chatbot.is_emergency(text), text)

    def test_spelling_variation(self):
        self.assertTrue(chatbot.is_emergency("mujhe sans nahi aa rahi"))
        self.assertTrue(chatbot.is_emergency("CHEST PAIN!!!"))

    def test_no_false_alarms_from_substrings(self):
        for text in ["I will be ill if I skip breakfast", "a brush stroke on my painting", "my keystroke counter",
                     "what a stroke of luck", "my heart is broken after a breakup", "I have a mild headache"]:
            self.assertFalse(chatbot.is_emergency(text), text)

    def test_self_harm_gets_its_own_supportive_reply(self):
        text, urgency, source = chatbot.get_reply("I want to kill myself")
        self.assertEqual((urgency, source), ("emergency", "builtin"))
        self.assertIn("1122", text)
        self.assertNotIn("medical emergency", text.lower())

    def test_emergency_reply_matches_language(self):
        self.assertIn("Foran", chatbot.get_reply("mujhe saans nahi aa rahi")[0])
        self.assertIn("فوراً", chatbot.get_reply("مجھے سانس نہیں آ رہی")[0])


class ScopeTests(SimpleTestCase):
    def test_roman_urdu_health_is_not_refused(self):
        with mock.patch.object(chatbot, "_call_openai", side_effect=RuntimeError("down")):
            text, _, source = chatbot.get_reply("mujhe do din se bukhar hai")
        self.assertEqual(source, "builtin")
        self.assertNotIn("only help with", text)

    def test_health_message_with_place_word_is_not_a_map_link(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="Rest and drink water."):
            text, _, source = chatbot.get_reply("the pharmacy gave me tablets and now my stomach hurts")
        self.assertEqual(source, "ai")

    def test_near_me_still_returns_map_links(self):
        self.assertIn("google.com/maps", chatbot.get_reply("pharmacy near me")[0])

    def test_off_topic_never_reaches_the_ai(self):
        with mock.patch.object(chatbot, "_call_openai") as call:
            chatbot.get_reply("write a python function to sort a list")
            call.assert_not_called()


class LiveReplyParsingTests(SimpleTestCase):
    def test_urgency_tag_is_read_and_removed(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="[URGENCY: urgent]\nSee a doctor soon."):
            text, urgency, _ = chatbot.get_reply("my knee has been swollen for a week")
        self.assertEqual(urgency, "urgent")
        self.assertNotIn("[URGENCY", text)

    def test_model_emergency_without_1122_gets_emergency_prefix(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="[URGENCY: emergency]\nGo to hospital."):
            text, urgency, _ = chatbot.get_reply("I feel very strange and weak on one side")
        self.assertEqual(urgency, "emergency")
        self.assertIn("1122", text)

    def test_missing_tag_falls_back_to_marker_detection(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="You should see a doctor soon."):
            _, urgency, _ = chatbot.get_reply("my knee has been swollen for a week")
        self.assertEqual(urgency, "urgent")

    def test_bare_off_topic_word_is_replaced(self):
        with mock.patch.object(chatbot, "_call_openai", return_value="OFF_TOPIC"):
            text, _, _ = chatbot.get_reply("tell me about my health insurance paperwork")
        self.assertIn("health questions", text)
