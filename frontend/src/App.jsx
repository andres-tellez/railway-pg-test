import { Routes, Route } from "react-router-dom";
import OnboardScreen from "./OnboardScreen";
import AskGptMvpUI from "./AskGptMvpUI";
import PostOAuthSync from "./PostOAuthSync";
import PostOAuthSuccess from "./PostOAuthSuccess"; // ✅ make sure this exists

function App() {
  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <Routes>
        <Route path="/" element={<OnboardScreen />} />
        <Route path="/ask" element={<AskGptMvpUI />} />
        <Route path="/post-oauth" element={<PostOAuthSuccess />} /> {/* ✅ Use the correct component */}
        {/* Optional: <Route path="/sync" element={<PostOAuthSync />} /> if needed */}
      </Routes>
    </div>
  );
}

export default App;
