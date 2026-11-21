import { createRoot } from "react-dom/client";
import { AuthProvider, useAuth } from "./auth";
import { AuthScreen } from "./components/AuthScreen";
import { ChatScreen } from "./components/ChatScreen";
import "./styles.css";

function App() {
  const { loading, session } = useAuth();
  if (loading)
    return (
      <div className="app-loading" role="status">
        <span className="spinner" />
        Открываем Partner Agent
      </div>
    );
  return session ? (
    <ChatScreen key={session.user.id} session={session} />
  ) : (
    <AuthScreen />
  );
}

createRoot(document.getElementById("root")!).render(
  <AuthProvider>
    <App />
  </AuthProvider>,
);
