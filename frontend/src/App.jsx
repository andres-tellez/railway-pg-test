import { Routes, Route } from "react-router-dom";
import OnboardScreen from "./OnboardScreen";
import AskGptMvpUI from "./AskGptMvpUI";
import PostOAuthSync from "./PostOAuthSync";
import PostOAuthSuccess from "./PostOAuthSuccess";
import AuthLogin from "./AuthLogin"; // ✅ newly added

function App() {
  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <Routes>
        <Route path="/" element={<OnboardScreen />} />
        <Route path="/ask" element={<AskGptMvpUI />} />
        <Route path="/post-oauth" element={<PostOAuthSuccess />} />
        <Route path="/auth/login" element={<AuthLogin />} /> {/* ✅ new route */}
        {/* Optional: <Route path="/sync" element={<PostOAuthSync />} /> */}
      </Routes>
    </div>
  );
}

export default App;
