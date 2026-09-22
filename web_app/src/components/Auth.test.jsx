import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Auth from "./Auth";

afterEach(() => cleanup());

const baseConfig = {
  company_email_domain: "sims.healthcare",
  password_reset_minutes: 30,
  password_reset_self_service: true,
};

function renderAuth(overrides = {}) {
  const api = vi.fn();
  const onAuth = vi.fn();
  const companyEmail = vi.fn((value, domain) => value.trim().toLowerCase().endsWith(`@${domain}`));
  render(
    <Auth
      api={api}
      companyEmail={companyEmail}
      config={{ ...baseConfig, ...(overrides.config || {}) }}
      onAuth={onAuth}
    />,
  );
  return { api, onAuth, companyEmail };
}

test("submits login credentials through the API", async () => {
  const user = userEvent.setup();
  const { api, onAuth } = renderAuth();
  const authResult = { access_token: "token-1", user: { id: "u1", username: "Jane", role: "User" } };
  api.mockResolvedValueOnce(authResult);

  await user.type(screen.getByLabelText("Company email"), "jane@sims.healthcare");
  await user.type(screen.getByLabelText("Password"), "secret123");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  expect(api).toHaveBeenCalledWith("/login", {
    method: "POST",
    body: { email: "jane@sims.healthcare", password: "secret123" },
  });
  expect(onAuth).toHaveBeenCalledWith(authResult);
});

test("shows backend-configured company domain in the auth form", () => {
  renderAuth({ config: { company_email_domain: "med360.test" } });
  expect(screen.getByPlaceholderText("you@med360.test")).toBeInTheDocument();
});

test("escapes multi-dot company domains in the email pattern", () => {
  renderAuth({ config: { company_email_domain: "auth.dev.med360.test" } });
  expect(screen.getByLabelText("Company email")).toHaveAttribute("pattern", String.raw`[^@\s]+@auth\.dev\.med360\.test`);
});

test("keeps forgot-password entry point visible when self-service reset is disabled", () => {
  renderAuth({ config: { password_reset_self_service: false } });
  expect(screen.getByRole("button", { name: "Forgot password?" })).toBeInTheDocument();
});

test("limits registration to administrators when self-registration is disabled", async () => {
  const user = userEvent.setup();
  renderAuth({ config: { allow_self_registration: false } });

  await user.click(screen.getByRole("button", { name: "New to WorkHub? Create an account" }));

  expect(screen.getByText("Employee self-registration is disabled. Only administrators with the bootstrap key can create an account here.")).toBeInTheDocument();
  expect(screen.getByLabelText("Account type")).toHaveDisplayValue("Manager");
  expect(screen.queryByRole("option", { name: "Employee" })).not.toBeInTheDocument();
  expect(screen.getByLabelText("Manager bootstrap key")).toBeInTheDocument();
});
