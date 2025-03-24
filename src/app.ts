import { APIGatewayProxyEvent, APIGatewayProxyResult } from "aws-lambda";
import { PrismaClient } from "./prisma";

const prisma = new PrismaClient();

console.log("HELLO_WORLD");

export const lambdaHandlerfgfd = async (
  event?: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  logger("HELLO_WORLD");
  let response: APIGatewayProxyResult;

  console.log("HELLO_WORLD");
  try {
    const user = await prisma.user.create({
      data: {
        name: "Alice",
        email: "alice@prisma.io123",
      },
    });

    response = {
      statusCode: 200,
      body: JSON.stringify({
        message: `hello world from function1 qwerwtr123`,
      }),
    };
  } catch (err: unknown) {
    console.error(err);
    response = {
      statusCode: 500,
      body: JSON.stringify({
        message: err instanceof Error ? err.message : "some error happened",
      }),
    };
  }

  return response;
};
