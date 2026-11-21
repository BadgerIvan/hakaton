import { useState } from "react";
import type { FormEvent } from "react";
import {
  Eye,
  EyeOff,
  LoaderCircle,
  MessageCircle,
  ShieldCheck,
} from "lucide-react";
import { useAuth } from "../auth";
import { errorMessage } from "../lib/api";

export function AuthScreen() {
  const auth = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [visible, setVisible] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const registering = mode === "register";

  function switchMode(next: "login" | "register") {
    setMode(next);
    setError("");
    setPassword("");
    setConfirmation("");
    setVisible(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    if (registering && password !== confirmation) {
      setError("Пароли не совпадают. Проверьте повтор пароля.");
      return;
    }
    setPending(true);
    setError("");
    try {
      if (registering) await auth.register(name.trim(), email.trim(), password);
      else await auth.login(email.trim(), password);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-story" aria-label="О Partner Agent">
        <div className="partner-logos">
          <img
            className="cft-logo"
            src="/cft.svg"
            alt="Центр финансовых технологий"
          />
          <span className="logo-divider" />
          <img className="shift-logo" src="/shift.svg" alt="ШИФТ" />
        </div>
        <div className="auth-story-copy">
          <span className="product-label">Partner Agent</span>
          <h1>
            Ответы о ЦФТ.
            <br />
            <span>Возможности ШИФТ.</span>
          </h1>
          <p>
            Разберитесь в продуктах ЦФТ и возможностях ШИФТ. Задавайте вопросы,
            уточняйте детали и находите ответы с источниками.
          </p>
          <div className="story-example">
            <MessageCircle size={23} aria-hidden="true" />
            <span>«Знаю Python. С чего начать в ШИФТ?»</span>
          </div>
        </div>
        <div className="auth-story-bottom">
          <ShieldCheck size={18} aria-hidden="true" />
          Личный аккаунт для ваших диалогов
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-form-wrap">
          <div className="auth-mode" aria-label="Вход или регистрация">
            <button
              type="button"
              className={!registering ? "selected" : ""}
              onClick={() => switchMode("login")}
              disabled={pending}
              aria-pressed={!registering}
            >
              Вход
            </button>
            <button
              type="button"
              className={registering ? "selected" : ""}
              onClick={() => switchMode("register")}
              disabled={pending}
              aria-pressed={registering}
            >
              Регистрация
            </button>
          </div>
          <h2>{registering ? "Давайте познакомимся" : "С возвращением"}</h2>
          <p className="auth-description">
            {registering
              ? "Создайте аккаунт, чтобы начать разговор."
              : "Войдите, чтобы продолжить разговор."}
          </p>
          {auth.restoreError && !error && (
            <div className="form-error" role="alert">
              {auth.restoreError}
            </div>
          )}
          <form onSubmit={submit} className="auth-form">
            {registering && (
              <label htmlFor="name">
                Ваше имя
                <input
                  id="name"
                  name="name"
                  autoComplete="name"
                  placeholder="Как к вам обращаться?"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                  minLength={2}
                  maxLength={80}
                  disabled={pending}
                />
              </label>
            )}
            <label htmlFor="email">
              Электронная почта
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                autoCapitalize="none"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                maxLength={254}
                disabled={pending}
              />
            </label>
            <label htmlFor="password">
              Пароль
              <span className="password-field">
                <input
                  id="password"
                  name="password"
                  type={visible ? "text" : "password"}
                  autoComplete={
                    registering ? "new-password" : "current-password"
                  }
                  placeholder={
                    registering ? "Не менее 8 символов" : "Введите пароль"
                  }
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  minLength={registering ? 8 : 1}
                  maxLength={128}
                  disabled={pending}
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setVisible(!visible)}
                  aria-label={visible ? "Скрыть пароль" : "Показать пароль"}
                >
                  {visible ? <EyeOff size={19} /> : <Eye size={19} />}
                </button>
              </span>
            </label>
            {registering && (
              <label htmlFor="confirmation">
                Повторите пароль
                <input
                  id="confirmation"
                  name="confirmation"
                  type={visible ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Ещё раз тот же пароль"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  required
                  minLength={8}
                  maxLength={128}
                  disabled={pending}
                />
              </label>
            )}
            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}
            <button
              className="primary-button auth-submit"
              type="submit"
              disabled={pending}
            >
              {pending ? (
                <>
                  <LoaderCircle className="spin" size={19} />
                  Подождите…
                </>
              ) : registering ? (
                "Создать аккаунт"
              ) : (
                "Войти"
              )}
            </button>
          </form>
          <p className="auth-switch">
            {registering ? "Уже есть аккаунт?" : "Первый раз здесь?"}{" "}
            <button
              type="button"
              disabled={pending}
              onClick={() => switchMode(registering ? "login" : "register")}
            >
              {registering ? "Войти" : "Создать аккаунт"}
            </button>
          </p>
        </div>
      </section>
    </main>
  );
}
