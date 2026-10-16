import React from "react";
import { render, screen } from "@testing-library/react";
import { Lock } from "lucide-react";
import FeatureCard from "./FeatureCard";

describe("FeatureCard", () => {
  const defaultProps = {
    title: "Test Feature",
    description: "This is a test feature description",
  };

  it("renders with title and description", () => {
    render(<FeatureCard {...defaultProps} />);

    expect(screen.getByText("Test Feature")).toBeInTheDocument();
    expect(
      screen.getByText("This is a test feature description")
    ).toBeInTheDocument();
  });

  it("renders with an icon when provided", () => {
    const { container } = render(
      <FeatureCard
        {...defaultProps}
        icon={<Lock data-testid="feature-icon" size={32} />}
      />
    );

    expect(screen.getByTestId("feature-icon")).toBeInTheDocument();
  });

  it("does not render icon container when icon is not provided", () => {
    const { container } = render(<FeatureCard {...defaultProps} />);

    // The icon container should not be in the DOM when no icon is provided
    const iconContainer = container.querySelector(".mb-4.flex");
    expect(iconContainer).not.toBeInTheDocument();
  });

  it("applies correct styling classes to the card", () => {
    const { container } = render(<FeatureCard {...defaultProps} />);

    const card = container.firstChild;
    expect(card).toHaveClass("rounded-lg");
    expect(card).toHaveClass("border");
    expect(card).toHaveClass("border-slate-700");
    expect(card).toHaveClass("bg-slate-800");
    expect(card).toHaveClass("bg-opacity-50");
    expect(card).toHaveClass("p-6");
    expect(card).toHaveClass("transition-all");
    expect(card).toHaveClass("duration-300");
  });

  it("applies correct styling classes to the title", () => {
    const { container } = render(<FeatureCard {...defaultProps} />);

    const title = screen.getByText("Test Feature");
    expect(title).toHaveClass("text-lg");
    expect(title).toHaveClass("font-semibold");
    expect(title).toHaveClass("text-white");
  });

  it("applies correct styling classes to the description", () => {
    const { container } = render(<FeatureCard {...defaultProps} />);

    const description = screen.getByText("This is a test feature description");
    expect(description).toHaveClass("text-slate-400");
    expect(description).toHaveClass("leading-relaxed");
  });

  it("renders icon with proper spacing when provided", () => {
    const { container } = render(
      <FeatureCard
        {...defaultProps}
        icon={<Lock data-testid="feature-icon" size={32} />}
      />
    );

    const iconContainer = container.querySelector(".mb-4.flex");
    expect(iconContainer).toHaveClass("flex");
    expect(iconContainer).toHaveClass("items-center");
    expect(iconContainer).toHaveClass("justify-start");
  });

  it("supports long descriptions without breaking layout", () => {
    const longDescription =
      "This is a very long description that should wrap properly without breaking the layout. It tests that the component can handle multiple lines of text gracefully.";

    render(
      <FeatureCard title="Test Feature" description={longDescription} />
    );

    expect(screen.getByText(longDescription)).toBeInTheDocument();
  });

  it("handles special characters in title and description", () => {
    const specialTitle = "Feature & Security™";
    const specialDescription = "Protects your data — safely & securely";

    render(
      <FeatureCard
        title={specialTitle}
        description={specialDescription}
      />
    );

    expect(screen.getByText(specialTitle)).toBeInTheDocument();
    expect(screen.getByText(specialDescription)).toBeInTheDocument();
  });
});
