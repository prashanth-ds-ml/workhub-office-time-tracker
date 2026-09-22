import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Forms from "./Forms";

afterEach(() => cleanup());

const baseConfig = {
  company_email_domain: "sims.healthcare",
};

const eventColors = {
  WORKING_DAY: "blue",
  HOLIDAY: "purple",
};

function renderForms(overrides = {}) {
  const api = vi.fn();
  const onClose = vi.fn();
  const onDone = vi.fn();
  render(
    <Forms
      api={api}
      config={{ ...baseConfig, ...(overrides.config || {}) }}
      eventColors={eventColors}
      normalizeIsoDate={value => value}
      onClose={onClose}
      onDone={onDone}
      policy={overrides.policy}
      today={() => "2026-07-02"}
      token="token-1"
      type={overrides.type || "employee"}
    />,
  );
  return { api, onClose, onDone };
}

test("uses backend-configured company domain in employee form", () => {
  renderForms({ config: { company_email_domain: "med360.test" } });
  expect(screen.getByPlaceholderText("employee@med360.test")).toBeInTheDocument();
});

test("escapes multi-dot company domains in the employee email pattern", () => {
  renderForms({ config: { company_email_domain: "staff.dev.med360.test" } });
  expect(screen.getByLabelText("Company email")).toHaveAttribute("pattern", String.raw`[^@\s]+@staff\.dev\.med360\.test`);
});

test("submits employee creation payload and closes on success", async () => {
  const user = userEvent.setup();
  const { api, onClose, onDone } = renderForms();
  api.mockResolvedValueOnce({ id: "u1" });

  await user.type(screen.getByLabelText("Full name"), "Managed User");
  await user.type(screen.getByLabelText("Company email"), "managed@sims.healthcare");
  await user.type(screen.getByLabelText("Temporary password"), "secret123");
  await user.selectOptions(screen.getByLabelText("Role"), "Manager");
  await user.type(screen.getByLabelText("Manager bootstrap key"), "manager-key");
  await user.type(screen.getByLabelText("Security question"), "First pet's name?");
  await user.type(screen.getByLabelText("Security answer"), "Rex");
  await user.click(screen.getByRole("button", { name: "Save changes" }));

  expect(api).toHaveBeenCalledWith("/admin/users", {
    token: "token-1",
    method: "POST",
    body: {
      username: "Managed User",
      email: "managed@sims.healthcare",
      password: "secret123",
      role: "Manager",
      bootstrap_secret: "manager-key",
      security_question: "First pet's name?",
      security_answer: "Rex",
    },
  });
  expect(onDone).toHaveBeenCalled();
  expect(onClose).toHaveBeenCalled();
});

test("blocks empty event dates before calling the API", async () => {
  const user = userEvent.setup();
  const { api, onClose, onDone } = renderForms({ type: "event" });

  await user.clear(screen.getByLabelText("Date"));
  await user.click(screen.getByRole("button", { name: "Save changes" }));

  expect(api).not.toHaveBeenCalled();
  expect(onDone).not.toHaveBeenCalled();
  expect(onClose).not.toHaveBeenCalled();
});
