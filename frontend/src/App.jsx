import { Routes, Route } from "react-router-dom";
import OnboardScreen from "./OnboardScreen";
import AskGptMvpUI from "./AskGptMvpUI";
import PostOAuthSync from "./PostOAuthSync";
import PostOAuthSuccess from "./PostOAuthSuccess"; // ✅ make sure this exists
import LoginPage from "./components/LoginPage";

function App() {
  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <Routes>
        <Route path="/" element={<OnboardScreen />} />
        <Route path="/auth/login" element={<LoginPage />} />
        <Route path="/auth/callback" element={<PostOAuthSuccess />} /> {/* 🔥 correct! */}
        <Route path="/ask" element={<AskGptMvpUI />} />
      </Routes>
    </div>
  );
}

export default App;
