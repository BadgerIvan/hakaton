import { useAuth } from "./auth";
import { AuthScreen } from "./components/AuthScreen";
import { ChatScreen } from "./components/ChatScreen";

export function App() {
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
