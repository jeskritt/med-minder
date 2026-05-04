import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { client } from "@/lib/api";
import { meQueryKey } from "@/lib/auth";

const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginInput = z.infer<typeof loginSchema>;

const GENERIC_ERROR = "Email or password is incorrect.";

export const Route = createFileRoute("/login")({
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>();

  const loginMutation = useMutation({
    mutationFn: async (input: LoginInput) => {
      const { response, error } = await client.POST("/auth/login", {
        body: input,
      });
      if (response.status === 401 || error) {
        throw new Error(GENERIC_ERROR);
      }
    },
    onSuccess: async () => {
      setServerError(null);
      await queryClient.invalidateQueries({ queryKey: [...meQueryKey] });
      void navigate({ to: "/medications" });
    },
    onError: (err: Error) => {
      setServerError(err.message);
    },
  });

  const onSubmit = (input: LoginInput) => {
    const parsed = loginSchema.safeParse(input);
    if (!parsed.success) {
      return;
    }
    setServerError(null);
    loginMutation.mutate(parsed.data);
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="w-full max-w-sm rounded border bg-white p-6 shadow"
        aria-label="Sign in"
        noValidate
      >
        <h1 className="mb-6 text-2xl font-bold">Sign in to MedMinder</h1>

        <div className="mb-4">
          <label htmlFor="email" className="block text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            className="mt-1 w-full rounded border px-3 py-2"
            {...register("email", { required: "Email is required" })}
          />
          {errors.email && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.email.message}
            </p>
          )}
        </div>

        <div className="mb-4">
          <label htmlFor="password" className="block text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className="mt-1 w-full rounded border px-3 py-2"
            {...register("password", { required: "Password is required" })}
          />
          {errors.password && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.password.message}
            </p>
          )}
        </div>

        {serverError && (
          <p role="alert" className="mb-4 text-sm text-red-600">
            {serverError}
          </p>
        )}

        <button
          type="submit"
          disabled={isSubmitting || loginMutation.isPending}
          className="w-full rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {loginMutation.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
