function [Centers,Radius_s,errormaps,erms] = sphereFit(X,Y,Z)


Centers = zeros([size(X,3) 3]);
Radius_s = zeros([size(X,3) 1]);
errormaps = X*0;
erms = zeros([size(X,3) 1]);
for i = 1:size(X,3)

    Index = ~isnan(X(:,:,i))>0;

    aux1 = X(:,:,i); aux2 = Y(:,:,i); aux3 = Z(:,:,i); 
    points_s = [aux1(Index(:)) aux2(Index(:)) aux3(Index(:))];
    [Center,  Radius ] = sphereFit_1(points_s);
    Centers(i,:) =  Center;
    Radius_s(i) = Radius;

    xc = Center(1); yc = Center(2); zc = Center(3);
    errormaps(:,:,i) =  sqrt((X(:,:,i)-xc).^2+(Y(:,:,i)-yc).^2+(Z(:,:,i)-zc).^2)-Radius;
    
    erms(i) = sqrt(mean(errormaps(:,:,i).^2,[1 2],'omitnan'));
%     erms(i) = mean(abs(errormaps(:,:,i)),[1 2],'omitnan');

end


end





function [Center,Radius] = sphereFit_1(X)
% this fits a sphere to a collection of data using a closed form for the
% solution (opposed to using an array the size of the data set). 
% Minimizes Sum((x-xc)^2+(y-yc)^2+(z-zc)^2-r^2)^2
% x,y,z are the data, xc,yc,zc are the sphere's center, and r is the radius

% Assumes that points are not in a singular configuration, real numbers, ...
% if you have coplanar data, use a circle fit with svd for determining the
% plane, recommended Circle Fit (Pratt method), by Nikolai Chernov
% http://www.mathworks.com/matlabcentral/fileexchange/22643

% Input:
% X: n x 3 matrix of cartesian data
% Outputs:
% Center: Center of sphere 
% Radius: Radius of sphere
% Author:
% Alan Jennings, University of Dayton

A=[mean(X(:,1).*(X(:,1)-mean(X(:,1)))), ...
    2*mean(X(:,1).*(X(:,2)-mean(X(:,2)))), ...
    2*mean(X(:,1).*(X(:,3)-mean(X(:,3)))); ...
    0, ...
    mean(X(:,2).*(X(:,2)-mean(X(:,2)))), ...
    2*mean(X(:,2).*(X(:,3)-mean(X(:,3)))); ...
    0, ...
    0, ...
    mean(X(:,3).*(X(:,3)-mean(X(:,3))))];
A=A+A.';
B=[mean((X(:,1).^2+X(:,2).^2+X(:,3).^2).*(X(:,1)-mean(X(:,1))));...
    mean((X(:,1).^2+X(:,2).^2+X(:,3).^2).*(X(:,2)-mean(X(:,2))));...
    mean((X(:,1).^2+X(:,2).^2+X(:,3).^2).*(X(:,3)-mean(X(:,3))))];
Center=(A\B).';
Radius=sqrt(mean(sum([X(:,1)-Center(1),X(:,2)-Center(2),X(:,3)-Center(3)].^2,2)));
end